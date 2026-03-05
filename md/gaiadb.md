锁等待：show status like 'innodb_row_lock%';

性能分析：show session status like '%handler%';

​     select * from performance_schema.data_locks\G;

SELECT * FROM performance_schema.data_lock_waits\G;

​     select * from information_schema.innodb_trx;

 SELECT * FROM sys.`innodb_lock_waits` \G

​     SHOW PROFILES ;

​     SHOW PROFILE FOR QUERY #{id};

​     SHOW ENGINE INNODB STATUS\G;

​     show processlist;

​     

SET optimizer_trace="enabled=on"

select * from t1, t2, t3, t4 where t2.t1_id = t1.id and t3.t2_id = t2.id and t4.t3_id = t3.id;

SELECT * FROM INFORMATION_SCHEMA.OPTIMIZER_TRACE\G;

SET optimizer_trace="enabled=off";

SELECT * FROM information_schema.processlist WHERE command != 'Sleep' and time>1 and user <> 'system user' and user <> 'replicator' order by time

mgr切换主：select group_replication_set_as_primary('4f87effa-21fd-11ed-b205-3cecef4e150a')

mgr设置debug模式：set global group_replication_communication_debug_options = GCS_DEBUG_ALL;

./mtr --suite=group_replication --extern host=172.18.120.23 --extern port=3309 --extern user=repl --extern password=repl4MGR --record --force example.1

执行如下语句打开 bison 的debug 模式：set debug = "d,parser_debug";

​                  set debug = 'd,info,/home/yjydev/mysqld.trace';

​                  set session debug='+d, simulate_random_io_thd_wait_for_disk_space';

SET SESSION debug = '+d,skip_dd_table_access_check'

select name from mysql.tables where hidden='System' and type='BASE TABLE';

ALTER INSTANCE {ENABLE | DISABLE} INNODB REDO_LOG

select * from performance_schema.innodb_redo_log_files;

show binlog events in 'binlog.000001';

SHOW ENGINE INNODB STATUS;

SHOW VARIABLES LIKE 'optimizer_switch';



select * from INFORMATION_SCHEMA.INNODB_BUFFER_PAGE；//统计inndob的page信息



查找内存占比高的模块：select event_name,current_number_of_bytes_used/1024/1024 from performance_schema.memory_summary_global_by_event_name order by current_number_of_bytes_used desc;

查看临时文件信息：SELECT * FROM information_schema.innodb_session_temp_tablespaces ;

查询redolog使用情况：select * from performance_schema.innodb_redo_log_files;

查找表空间信息：select * from information_schema.tables where table_schema = 'test'and table_name = 't2'\G;

查看更详细的日志信息：SET GLOBAL innodb_print_ddl_logs = 1; //输出ddl的相关信息

​                  SET GLOBAL log_error_verbosity = 3; //info信息也会输出到errorlog中

查看table属性

SELECT * FROM information_schema.tables WHERE table_schema = 'test'\G;

随机插入数据

CREATE TABLE t0(

a INT PRIMARY KEY,

b INT) ENGINE=InnoDB;

DELIMITER //

CREATE PROCEDURE populate_t0()

BEGIN

   DECLARE i int DEFAULT 1;

   WHILE (i <= $table_size) DO

​       INSERT INTO t0 VALUES (i, 1000000 * RAND());

​       SET i = i + 1;

   END WHILE;

END //

DELIMITER ;

CALL populate_t0() ;