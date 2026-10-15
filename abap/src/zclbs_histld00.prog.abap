*&---------------------------------------------------------------------*
*& Report ZCLBS_HISTLD00
*&---------------------------------------------------------------------*
*& Position history load: ZCLBS_TRANHIST -> ZCLBS_POSHIST.
*& Migrated from src/programs/batch/HISTLD00.cbl (VSAM TRANHIST -> DB2
*& POSHIST). Paragraph names of the COBOL source are kept in comments
*& so the two programs can be compared side by side.
*&---------------------------------------------------------------------*
REPORT zclbs_histld00.

TYPES ty_count TYPE i.

PARAMETERS:
  p_prcdt  TYPE d,
  p_seqno  TYPE n LENGTH 4,
  p_commit TYPE i DEFAULT 1000 OBLIGATORY,
  p_maxerr TYPE i DEFAULT 100 OBLIGATORY,
  p_maxrc  TYPE i DEFAULT 4 OBLIGATORY.

"! Error reporting (COBOL: CALL 'ERRPROC' USING ERR-MESSAGE)
INTERFACE lif_error_handler.
  METHODS log_error
    IMPORTING
      iv_program TYPE syrepid
      iv_text    TYPE csequence.
ENDINTERFACE.

"! Unit-of-work control (COBOL: EXEC SQL COMMIT/ROLLBACK WORK)
INTERFACE lif_transaction.
  METHODS commit.
  METHODS rollback.
ENDINTERFACE.

CLASS lcl_transaction DEFINITION FINAL.
  PUBLIC SECTION.
    INTERFACES lif_transaction.
ENDCLASS.

CLASS lcl_transaction IMPLEMENTATION.
  METHOD lif_transaction~commit.
    COMMIT WORK.
  ENDMETHOD.

  METHOD lif_transaction~rollback.
    ROLLBACK WORK.
  ENDMETHOD.
ENDCLASS.

"! ERRPROC equivalent: writes the error block to the list (spool) and the
"! job log. Neither is affected by ROLLBACK WORK, like the ERRLOG file.
CLASS lcl_joblog_error_handler DEFINITION FINAL.
  PUBLIC SECTION.
    INTERFACES lif_error_handler.
ENDCLASS.

CLASS lcl_joblog_error_handler IMPLEMENTATION.
  METHOD lif_error_handler~log_error.
    DATA lv_timestamp TYPE timestampl.
    GET TIME STAMP FIELD lv_timestamp.

    WRITE: / '====================================================',
           / 'ERROR DETECTED:', lv_timestamp TIME ZONE 'UTC',
           / 'PROGRAM:       ', iv_program,
           / 'MESSAGE:       ', iv_text,
           / '===================================================='.

    MESSAGE |{ iv_program }: { iv_text }| TYPE 'S'.
  ENDMETHOD.
ENDCLASS.

CLASS lcl_history_loader DEFINITION FINAL.
  PUBLIC SECTION.
    TYPES:
      BEGIN OF ty_stats,
        records_read    TYPE ty_count,
        records_written TYPE ty_count,
        error_count     TYPE ty_count,
        return_code     TYPE ty_count,
      END OF ty_stats.

    CONSTANTS:
      c_program_id    TYPE syrepid VALUE 'HISTLD00',
      c_db2_error_pgm TYPE syrepid VALUE 'DB2ERROR',
      c_status_active TYPE zclbs_bchctl-status VALUE 'A'.

    METHODS constructor
      IMPORTING
        io_transaction      TYPE REF TO lif_transaction
        io_error_handler    TYPE REF TO lif_error_handler
        iv_process_date     TYPE zclbs_bchctl-process_date
        iv_sequence_no      TYPE zclbs_bchctl-sequence_no
        iv_commit_threshold TYPE i DEFAULT 1000
        iv_max_errors       TYPE i DEFAULT 100
        iv_package_size     TYPE i DEFAULT 1000.

    "! 0000-MAIN
    METHODS run
      RETURNING
        VALUE(rs_stats) TYPE ty_stats.

  PRIVATE SECTION.
    TYPES ty_tranhist_tab TYPE STANDARD TABLE OF zclbs_tranhist WITH EMPTY KEY.

    DATA mo_transaction TYPE REF TO lif_transaction.
    DATA mo_error_handler TYPE REF TO lif_error_handler.
    DATA mv_process_date TYPE zclbs_bchctl-process_date.
    DATA mv_sequence_no TYPE zclbs_bchctl-sequence_no.
    DATA mv_commit_threshold TYPE i.
    DATA mv_max_errors TYPE i.
    DATA mv_package_size TYPE i.

    DATA ms_stats TYPE ty_stats.
    DATA mv_commit_count TYPE i.
    DATA mv_end_of_file TYPE abap_bool.

    DATA mt_buffer TYPE ty_tranhist_tab.
    DATA mv_buffer_index TYPE i.
    DATA ms_last_key TYPE zclbs_tranhist.
    DATA mv_first_package TYPE abap_bool VALUE abap_true.

    METHODS initialize.
    METHODS process.
    METHODS terminate.
    METHODS init_checkpoints.
    METHODS read_history
      RETURNING
        VALUE(rs_history) TYPE zclbs_tranhist.
    METHODS fetch_next_package.
    METHODS load_to_db
      IMPORTING
        is_history TYPE zclbs_tranhist.
    METHODS check_commit.
    METHODS update_checkpoint.
    METHODS final_commit.
    METHODS display_stats.
    METHODS error_routine
      IMPORTING
        iv_text TYPE csequence.
    METHODS db_error_routine
      IMPORTING
        ix_error TYPE REF TO cx_sy_open_sql_db.
ENDCLASS.

CLASS lcl_history_loader IMPLEMENTATION.
  METHOD constructor.
    mo_transaction = io_transaction.
    mo_error_handler = io_error_handler.
    mv_process_date = iv_process_date.
    mv_sequence_no = iv_sequence_no.
    mv_commit_threshold = iv_commit_threshold.
    mv_max_errors = iv_max_errors.
    mv_package_size = iv_package_size.
  ENDMETHOD.

  METHOD run.
    initialize( ).

    WHILE mv_end_of_file = abap_false AND ms_stats-error_count <= mv_max_errors.
      process( ).
    ENDWHILE.

    terminate( ).

    ms_stats-return_code = ms_stats-error_count.
    rs_stats = ms_stats.
  ENDMETHOD.

  "! 1000-INITIALIZE. 1100-OPEN-FILES and 1200-CONNECT-DB2 have no
  "! equivalent: both stores are DDIC tables on the default connection.
  METHOD initialize.
    init_checkpoints( ).
  ENDMETHOD.

  "! 2000-PROCESS
  METHOD process.
    DATA(ls_history) = read_history( ).

    IF mv_end_of_file = abap_false.
      load_to_db( ls_history ).
      check_commit( ).
    ENDIF.
  ENDMETHOD.

  "! 3000-TERMINATE. 3200-CLOSE-FILES / 3300-DISCONNECT-DB2 not needed.
  METHOD terminate.
    final_commit( ).
    display_stats( ).
  ENDMETHOD.

  "! 1300-INIT-CHECKPOINTS: READ + REWRITE of the control record with
  "! BCT-STATUS = BCT-STAT-ACTIVE. The VSAM rewrite was durable at once,
  "! so the status change is committed immediately.
  METHOD init_checkpoints.
    UPDATE zclbs_bchctl
      SET status = @c_status_active
      WHERE job_name     = @c_program_id
        AND process_date = @mv_process_date
        AND sequence_no  = @mv_sequence_no.

    IF sy-subrc <> 0.
      error_routine( 'Control record not found' ).
    ELSE.
      mo_transaction->commit( ).
    ENDIF.
  ENDMETHOD.

  "! 2100-READ-HISTORY: sequential read of the KSDS in TH-KEY order.
  METHOD read_history.
    IF lines( mt_buffer ) <= mv_buffer_index.
      fetch_next_package( ).
      IF mt_buffer IS INITIAL.
        mv_end_of_file = abap_true.
        RETURN.
      ENDIF.
    ENDIF.

    mv_buffer_index = mv_buffer_index + 1.
    rs_history = mt_buffer[ mv_buffer_index ].
    ms_last_key = rs_history.
    ms_stats-records_read = ms_stats-records_read + 1.
  ENDMETHOD.

  "! Keyset paging instead of a cursor: COMMIT WORK / ROLLBACK WORK close
  "! open ABAP SQL cursors, and the load commits every N records.
  METHOD fetch_next_package.
    CLEAR: mt_buffer, mv_buffer_index.

    IF mv_first_package = abap_true.
      mv_first_package = abap_false.
      SELECT * FROM zclbs_tranhist
        ORDER BY PRIMARY KEY
        INTO TABLE @mt_buffer
        UP TO @mv_package_size ROWS.
      RETURN.
    ENDIF.

    SELECT * FROM zclbs_tranhist
      WHERE trans_date > @ms_last_key-trans_date
         OR ( trans_date = @ms_last_key-trans_date
          AND trans_time > @ms_last_key-trans_time )
         OR ( trans_date   = @ms_last_key-trans_date
          AND trans_time   = @ms_last_key-trans_time
          AND portfolio_id > @ms_last_key-portfolio_id )
         OR ( trans_date   = @ms_last_key-trans_date
          AND trans_time   = @ms_last_key-trans_time
          AND portfolio_id = @ms_last_key-portfolio_id
          AND sequence_no  > @ms_last_key-sequence_no )
      ORDER BY PRIMARY KEY
      INTO TABLE @mt_buffer
      UP TO @mv_package_size ROWS.
  ENDMETHOD.

  "! 2200-LOAD-TO-DB2
  METHOD load_to_db.
    DATA ls_poshist TYPE zclbs_poshist.

    ls_poshist = VALUE #(
      account_no   = is_history-account_no
      portfolio_id = is_history-portfolio_id
      trans_date   = is_history-trans_date
      trans_time   = is_history-trans_time
      trans_type   = is_history-trans_type
      security_id  = is_history-security_id
      quantity     = is_history-quantity
      price        = is_history-price
      amount       = is_history-amount
      fees         = is_history-fees
      total_amount = is_history-total_amount
      cost_basis   = is_history-cost_basis
      gain_loss    = is_history-gain_loss
      process_date = sy-datum
      process_time = sy-uzeit
      program_id   = c_program_id
      user_id      = sy-uname ).
    GET TIME STAMP FIELD ls_poshist-audit_timestamp.

    TRY.
        INSERT zclbs_poshist FROM @ls_poshist.
        " sy-subrc = 4 is a duplicate key (DB2 SQLCODE -803): skipped,
        " neither written nor counted as an error.
        IF sy-subrc = 0.
          ms_stats-records_written = ms_stats-records_written + 1.
        ENDIF.
      CATCH cx_sy_open_sql_db INTO DATA(lx_error).
        ms_stats-error_count = ms_stats-error_count + 1.
        db_error_routine( lx_error ).
    ENDTRY.
  ENDMETHOD.

  "! 2300-CHECK-COMMIT
  METHOD check_commit.
    mv_commit_count = mv_commit_count + 1.

    IF mv_commit_count >= mv_commit_threshold.
      mo_transaction->commit( ).
      mv_commit_count = 0.
      update_checkpoint( ).
    ENDIF.
  ENDMETHOD.

  "! 2310-UPDATE-CHECKPOINT. The VSAM REWRITE was outside the DB2 unit of
  "! work, so the checkpoint is committed on its own right away.
  METHOD update_checkpoint.
    UPDATE zclbs_bchctl
      SET records_read    = @ms_stats-records_read,
          records_written = @ms_stats-records_written
      WHERE job_name     = @c_program_id
        AND process_date = @mv_process_date
        AND sequence_no  = @mv_sequence_no.

    IF sy-subrc <> 0.
      error_routine( 'Error updating checkpoint' ).
    ELSE.
      mo_transaction->commit( ).
    ENDIF.
  ENDMETHOD.

  "! 3100-FINAL-COMMIT
  METHOD final_commit.
    mo_transaction->commit( ).
    update_checkpoint( ).
  ENDMETHOD.

  "! 3400-DISPLAY-STATS
  METHOD display_stats.
    WRITE: / 'HISTLD00 Processing Statistics:',
           / '  Records Read:    ', ms_stats-records_read,
           / '  Records Written: ', ms_stats-records_written,
           / '  Errors:          ', ms_stats-error_count.

    MESSAGE |HISTLD00 read { ms_stats-records_read } | &&
            |written { ms_stats-records_written } | &&
            |errors { ms_stats-error_count }| TYPE 'S'.
  ENDMETHOD.

  "! 9000-ERROR-ROUTINE: log, then roll back the open unit of work.
  METHOD error_routine.
    mo_error_handler->log_error( iv_program = c_program_id
                                 iv_text    = iv_text ).
    mo_transaction->rollback( ).
  ENDMETHOD.

  "! DB2-ERROR-ROUTINE (DBPROC.cpy): roll back, then log the SQL error.
  METHOD db_error_routine.
    mo_transaction->rollback( ).
    mo_error_handler->log_error(
      iv_program = c_db2_error_pgm
      iv_text    = |SQLCODE: { ix_error->sqlcode } ERROR: { ix_error->get_text( ) }| ).
  ENDMETHOD.
ENDCLASS.

START-OF-SELECTION.
  DATA(go_loader) = NEW lcl_history_loader(
    io_transaction      = NEW lcl_transaction( )
    io_error_handler    = NEW lcl_joblog_error_handler( )
    iv_process_date     = p_prcdt
    iv_sequence_no      = p_seqno
    iv_commit_threshold = p_commit
    iv_max_errors       = p_maxerr ).

  DATA(gs_stats) = go_loader->run( ).

  " COBOL: MOVE WS-ERROR-COUNT TO RETURN-CODE. The JCL chain only runs the
  " next step when RC <= 4, so a higher RC cancels the background job.
  IF gs_stats-return_code > p_maxrc.
    IF sy-batch = abap_true.
      MESSAGE |HISTLD00 ended with return code { gs_stats-return_code }| TYPE 'E'.
    ELSE.
      MESSAGE |HISTLD00 ended with return code { gs_stats-return_code }|
        TYPE 'S' DISPLAY LIKE 'E'.
    ENDIF.
  ENDIF.

*&---------------------------------------------------------------------*
*& ABAP Unit tests (ABAP SQL test double framework, 7.51+)
*&---------------------------------------------------------------------*
CLASS ltd_transaction DEFINITION FINAL FOR TESTING.
  PUBLIC SECTION.
    INTERFACES lif_transaction.
    DATA mv_commits TYPE i.
    DATA mv_rollbacks TYPE i.
ENDCLASS.

CLASS ltd_transaction IMPLEMENTATION.
  METHOD lif_transaction~commit.
    mv_commits = mv_commits + 1.
  ENDMETHOD.

  METHOD lif_transaction~rollback.
    mv_rollbacks = mv_rollbacks + 1.
  ENDMETHOD.
ENDCLASS.

CLASS ltd_error_handler DEFINITION FINAL FOR TESTING.
  PUBLIC SECTION.
    INTERFACES lif_error_handler.
    DATA mt_messages TYPE string_table.
ENDCLASS.

CLASS ltd_error_handler IMPLEMENTATION.
  METHOD lif_error_handler~log_error.
    INSERT |{ iv_program }: { iv_text }| INTO TABLE mt_messages.
  ENDMETHOD.
ENDCLASS.

CLASS ltc_history_loader DEFINITION FINAL FOR TESTING
  RISK LEVEL HARMLESS
  DURATION SHORT.

  PRIVATE SECTION.
    TYPES ty_tranhist_tab TYPE STANDARD TABLE OF zclbs_tranhist WITH EMPTY KEY.
    TYPES ty_poshist_tab TYPE STANDARD TABLE OF zclbs_poshist WITH EMPTY KEY.
    TYPES ty_bchctl_tab TYPE STANDARD TABLE OF zclbs_bchctl WITH EMPTY KEY.

    CONSTANTS c_process_date TYPE d VALUE '20241231'.

    CLASS-DATA go_environment TYPE REF TO if_osql_test_environment.

    DATA mo_transaction TYPE REF TO ltd_transaction.
    DATA mo_errors TYPE REF TO ltd_error_handler.

    CLASS-METHODS class_setup.
    CLASS-METHODS class_teardown.
    METHODS setup.

    METHODS loads_and_maps_all_records FOR TESTING.
    METHODS skips_duplicate_keys FOR TESTING.
    METHODS commits_at_threshold FOR TESTING.
    METHODS pages_through_all_records FOR TESTING.
    METHODS missing_control_still_loads FOR TESTING.

    METHODS given_control_record.
    METHODS given_history
      IMPORTING
        it_history TYPE ty_tranhist_tab.
    METHODS history
      IMPORTING
        iv_date           TYPE d DEFAULT '20240115'
        iv_time           TYPE t DEFAULT '101500'
        iv_portfolio      TYPE zclbs_tranhist-portfolio_id DEFAULT 'PORT0001'
        iv_sequence       TYPE zclbs_tranhist-sequence_no DEFAULT '000001'
        iv_account        TYPE zclbs_tranhist-account_no DEFAULT 'ACCT0001'
      RETURNING
        VALUE(rs_history) TYPE zclbs_tranhist.
    METHODS three_records
      RETURNING
        VALUE(rt_history) TYPE ty_tranhist_tab.
    METHODS new_loader
      IMPORTING
        iv_commit_threshold TYPE i DEFAULT 1000
        iv_package_size     TYPE i DEFAULT 1000
      RETURNING
        VALUE(ro_loader)    TYPE REF TO lcl_history_loader.
    METHODS control_record
      RETURNING
        VALUE(rs_control) TYPE zclbs_bchctl.
ENDCLASS.

CLASS ltc_history_loader IMPLEMENTATION.
  METHOD class_setup.
    go_environment = cl_osql_test_environment=>create(
      i_dependency_list = VALUE #( ( 'ZCLBS_TRANHIST' )
                                   ( 'ZCLBS_POSHIST' )
                                   ( 'ZCLBS_BCHCTL' ) ) ).
  ENDMETHOD.

  METHOD class_teardown.
    go_environment->destroy( ).
  ENDMETHOD.

  METHOD setup.
    go_environment->clear_doubles( ).
    mo_transaction = NEW #( ).
    mo_errors = NEW #( ).
  ENDMETHOD.

  METHOD loads_and_maps_all_records.
    DATA lt_poshist TYPE ty_poshist_tab.

    given_control_record( ).
    given_history( three_records( ) ).

    DATA(ls_stats) = new_loader( )->run( ).

    cl_abap_unit_assert=>assert_equals( act = ls_stats-records_read exp = 3 ).
    cl_abap_unit_assert=>assert_equals( act = ls_stats-records_written exp = 3 ).
    cl_abap_unit_assert=>assert_equals( act = ls_stats-error_count exp = 0 ).
    cl_abap_unit_assert=>assert_equals( act = ls_stats-return_code exp = 0 ).
    cl_abap_unit_assert=>assert_initial( mo_errors->mt_messages ).

    SELECT * FROM zclbs_poshist ORDER BY PRIMARY KEY INTO TABLE @lt_poshist.
    cl_abap_unit_assert=>assert_equals( act = lines( lt_poshist ) exp = 3 ).

    DATA(ls_first) = lt_poshist[ 1 ].
    cl_abap_unit_assert=>assert_equals( act = ls_first-account_no exp = 'ACCT0001' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-portfolio_id exp = 'PORT0001' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-trans_date exp = '20240115' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-trans_time exp = '101500' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-trans_type exp = 'BU' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-security_id exp = 'US0378331005' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-quantity exp = '100.125' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-price exp = '187.250' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-amount exp = '18748.41' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-fees exp = '9.99' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-total_amount exp = '18758.40' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-cost_basis exp = '18000.00' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-gain_loss exp = '-250.50' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-program_id exp = 'HISTLD00' ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-user_id exp = sy-uname ).
    cl_abap_unit_assert=>assert_equals( act = ls_first-process_date exp = sy-datum ).
    cl_abap_unit_assert=>assert_not_initial( ls_first-audit_timestamp ).

    DATA(ls_control) = control_record( ).
    cl_abap_unit_assert=>assert_equals( act = ls_control-status exp = 'A' ).
    cl_abap_unit_assert=>assert_equals( act = ls_control-records_read exp = 3 ).
    cl_abap_unit_assert=>assert_equals( act = ls_control-records_written exp = 3 ).
  ENDMETHOD.

  METHOD skips_duplicate_keys.
    DATA lt_existing TYPE ty_poshist_tab.

    given_control_record( ).
    given_history( three_records( ) ).
    lt_existing = VALUE #( ( account_no   = 'ACCT0002'
                             portfolio_id = 'PORT0001'
                             trans_date   = '20240115'
                             trans_time   = '101600' ) ).
    go_environment->insert_test_data( lt_existing ).

    DATA(ls_stats) = new_loader( )->run( ).

    cl_abap_unit_assert=>assert_equals( act = ls_stats-records_read exp = 3 ).
    cl_abap_unit_assert=>assert_equals( act = ls_stats-records_written exp = 2 ).
    cl_abap_unit_assert=>assert_equals( act = ls_stats-error_count exp = 0 ).
    cl_abap_unit_assert=>assert_initial( mo_errors->mt_messages ).
    cl_abap_unit_assert=>assert_equals( act = mo_transaction->mv_rollbacks exp = 0 ).
  ENDMETHOD.

  METHOD commits_at_threshold.
    given_control_record( ).
    given_history( VALUE #( ( history( iv_sequence = '000001' iv_account = 'ACCT0001' ) )
                            ( history( iv_sequence = '000002' iv_account = 'ACCT0002' ) )
                            ( history( iv_sequence = '000003' iv_account = 'ACCT0003' ) )
                            ( history( iv_sequence = '000004' iv_account = 'ACCT0004' ) )
                            ( history( iv_sequence = '000005' iv_account = 'ACCT0005' ) ) ) ).

    DATA(ls_stats) = new_loader( iv_commit_threshold = 2 )->run( ).

    cl_abap_unit_assert=>assert_equals( act = ls_stats-records_written exp = 5 ).
    " 1 for the control status + (data + checkpoint) after records 2, 4
    " and at the final commit.
    cl_abap_unit_assert=>assert_equals( act = mo_transaction->mv_commits exp = 7 ).
    cl_abap_unit_assert=>assert_equals( act = mo_transaction->mv_rollbacks exp = 0 ).
  ENDMETHOD.

  METHOD pages_through_all_records.
    " Each record differs from its predecessor in a different key
    " component, so every keyset paging branch is exercised.
    given_control_record( ).
    given_history( VALUE #(
      ( history( iv_date = '20240301' iv_account = 'ACCT0005' ) )
      ( history( iv_sequence = '000002' iv_portfolio = 'PORT0002' iv_account = 'ACCT0004' ) )
      ( history( iv_portfolio = 'PORT0002' iv_account = 'ACCT0003' ) )
      ( history( iv_time = '120000' iv_account = 'ACCT0002' ) )
      ( history( iv_account = 'ACCT0001' ) ) ) ).

    DATA(ls_stats) = new_loader( iv_package_size = 2 )->run( ).

    cl_abap_unit_assert=>assert_equals( act = ls_stats-records_read exp = 5 ).
    cl_abap_unit_assert=>assert_equals( act = ls_stats-records_written exp = 5 ).
  ENDMETHOD.

  METHOD missing_control_still_loads.
    given_history( three_records( ) ).

    DATA(ls_stats) = new_loader( )->run( ).

    " Parity with HISTLD00: 9000-ERROR-ROUTINE logs and rolls back but does
    " not stop the run or count towards the return code.
    cl_abap_unit_assert=>assert_equals( act = ls_stats-records_written exp = 3 ).
    cl_abap_unit_assert=>assert_equals( act = ls_stats-return_code exp = 0 ).
    cl_abap_unit_assert=>assert_equals(
      act = mo_errors->mt_messages
      exp = VALUE string_table( ( `HISTLD00: Control record not found` )
                                ( `HISTLD00: Error updating checkpoint` ) ) ).
    cl_abap_unit_assert=>assert_equals( act = mo_transaction->mv_rollbacks exp = 2 ).
  ENDMETHOD.

  METHOD given_control_record.
    DATA lt_control TYPE ty_bchctl_tab.
    lt_control = VALUE #( ( job_name     = 'HISTLD00'
                            process_date = c_process_date
                            sequence_no  = '0001'
                            status       = 'R' ) ).
    go_environment->insert_test_data( lt_control ).
  ENDMETHOD.

  METHOD given_history.
    go_environment->insert_test_data( it_history ).
  ENDMETHOD.

  METHOD history.
    rs_history = VALUE #( trans_date   = iv_date
                          trans_time   = iv_time
                          portfolio_id = iv_portfolio
                          sequence_no  = iv_sequence
                          account_no   = iv_account
                          trans_type   = 'BU'
                          security_id  = 'US0378331005'
                          quantity     = '100.125'
                          price        = '187.250'
                          amount       = '18748.41'
                          fees         = '9.99'
                          total_amount = '18758.40'
                          cost_basis   = '18000.00'
                          gain_loss    = '-250.50' ).
  ENDMETHOD.

  METHOD three_records.
    rt_history = VALUE #( ( history( ) )
                          ( history( iv_time     = '101600'
                                     iv_sequence = '000002'
                                     iv_account  = 'ACCT0002' ) )
                          ( history( iv_time     = '101700'
                                     iv_sequence = '000003'
                                     iv_account  = 'ACCT0003' ) ) ).
  ENDMETHOD.

  METHOD new_loader.
    ro_loader = NEW #( io_transaction      = mo_transaction
                       io_error_handler    = mo_errors
                       iv_process_date     = c_process_date
                       iv_sequence_no      = '0001'
                       iv_commit_threshold = iv_commit_threshold
                       iv_package_size     = iv_package_size ).
  ENDMETHOD.

  METHOD control_record.
    SELECT SINGLE * FROM zclbs_bchctl
      WHERE job_name     = 'HISTLD00'
        AND process_date = @c_process_date
        AND sequence_no  = '0001'
      INTO @rs_control.
  ENDMETHOD.
ENDCLASS.
