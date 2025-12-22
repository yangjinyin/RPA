# 总流程

```c++
|-->do_command()
|	|-->dispatch_command()
|	|	|-->dispatch_sql_command()
|	|	|	|-->parse_sql()
|	|	|	|	|-->THD::sql_parser()
|	|	|	|	|	|-->LEX::make_sql_cmd()
|	|	|	|	|	|	|-->PT_create_table_stmt::make_cmd()....   
|	|	|	|-->mysql_execute_command()
|	|	|	|	|-->Sql_cmd_create_table::execute() .....
```



# create table

```c++
|-->create_table_impl()
|	|-->rea_create_tmp_table() //临时表
|	|-->rea_create_base_table() //普通表&&系统表
|	|	|-->1. dd::create_table() //dd表信息更新
|	|	|	|-->create_dd_system_table()
|	|	|	|-->create_dd_user_table()
|	|	|	|	|-->fill_dd_table_from_create_info()//create_info中信息设置到table dd表中
|	|	|-->2. ha_create_table() //innodb层更新表信息
|	|	|	|-->innobase_basic_ddl::create_impl()
|	|	|	|	|-->create_table_info_t::create_table() //解析表名
|	|	|	|	|-->create_table_info_t::create_table() 
|	|	|	|	|	|-->create_table_info_t::create_table_def()//innodb 填充 field 包括DB_ROW_ID,DB_ROLL_PTR..
|	|	|	|	|	|	|-->row_create_table_for_mysql() //
```



# Insert 流程

```c++
|-->Sql_cmd_insert_values::execute_inner()
|	|-->write_record()
|	|	|-->ha_write_row()
|	|	|	|-->ha_innobase::write_row()
|	|	|	|	|-->update_auto_increment() //自增逻辑处理
|	|	|	|	|-->row_insert_for_mysql()
|	|	|	|	|	|-->row_insert_for_mysql_using_ins_graph()
|	|	|	|	|	|	|-->row_mysql_convert_row_to_innobase() //mysql格式转innodb层格式
|	|	|	|	|	|	|-->row_ins_step()
|	|	|	|	|	|	|	|-->row_ins()
|	|	|	|	|	|	|	|	|-->row_ins_index_entry_step()
|	|	|	|	|	|	|	|	|	|-->row_ins_index_entry_set_vals()//将一个数据行（row）中的列值填充到索引条目
|	|	|	|	|	|	|	|	|	|-->row_ins_index_entry()
|	|	|	|	|	|	|	|	|	|	|...-->row_ins_clust_index_entry_low()//往主键b+树插入,乐观悲观插入
-------------------------------------------------------------------------------------------------
 ##innodb层 乐观插入
|-->btr_cur_optimistic_insert()
|	|-->btr_cur_ins_lock_and_undo() //1. 检查是否有gap锁等 2.生成undo log 3.生成redo-log 保护undo-log
|	|-->page_cur_tuple_insert()
|	|	|-->rec_convert_dtuple_to_rec() //将dtuple转换成物理记录格式rec
|	|	|-->rec_get_offsets() //记录page中的offset
|	|	|-->page_cur_insert_rec_low()
|	|	|	|-->1. rec_size = rec_offs_size(offsets)//从offsets中获得rec长度
|	|	|	|-->2. rec_get_offsets() //在page中找到可插入的位置：先在free_list中查找；如果没找到，则在heap上找
|	|	|	|-->3. rec_copy(insert_buf, rec, offsets)//将rec插入到找到的位置上
|	|	|	|-->4. page_rec_set_next(current_rec, insert_rec)//将insert_rec 插入到current_rec后面
|	|	|	|-->5. rec_set_n_owned_new(insert_rec, nullptr, 0)//修改insert_rec的n_owned为0..
|	|	|	|-->6. page_header_set_ptr()//更新page的元数据
|	|	|	|-->7. rec_set_n_owned_new(owner_rec, nullptr, n_owned + 1)//更新owner record的值
|	|	|	|-->8. page_cur_insert_rec_write_log()//写redo-log
----------------------------------------------------------------------------------------------------
##悲观插入
|-->btr_cur_pessimistic_insert()
|	|-->btr_cur_ins_lock_and_undo() //1. 检查是否有gap锁等 2.生成undo log 3.生成redo-log 保护undo-log
|	|-->btr_root_raise_and_insert() //根页面分裂&&insert
|	|-->btr_page_split_and_insert() //普通页分裂&&insert
|	|-->btr_search_update_hash_on_insert()//更新AHI哈希表信息
```



# mlog insert流程

```c++
|--> page_cur_insert_rec_write_log
|    |--> mlog_open_and_write_index
|    |    |--> //初始化日志记录
|    |    |--> mlog_write_initial_log_record_fast
|    |    |    |--> //mini-transaction相关的函数，用来将redo条目写入到redo log buffer
|    |    |    |--> //写入type,space,page_no
|    |    |    |--> mlog_write_initial_log_record_low
|    |    |--> log_index_column_counts
|    |    |    |-->//写入字段个数filed no，2个字节
|    |    |    |--> mach_write_to_2(log_ptr, n);
|    |    |    |-->//写入行记录上决定唯一性的列的个数 u_uniq，2个字节
|    |    |    |-->mach_write_to_2(log_ptr, dict_index_get_n_unique_in_tree(index))
|    |    |--> /loop/
|    |    |--> //写入每个字段的长度 filed_length
|    |    |--> mach_write_to_2(log_ptr, len);
|    |    |--> /end loop/
|    |--> //写入记录在page上的偏移量 current rec off，占两个字节
|    |--> mach_write_to_2(log_ptr, page_offset(cursor_rec));
|    |--> //mismatch len
|    |--> mach_write_compressed(log_ptr, 2 * (rec_size - i));
|    |--> //将插入的记录拷贝到redo文件 body，同时关闭mlog
|    |--> memcpy
|    |--> mlog_close
```

