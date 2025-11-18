# 1. 从 pull到push模型

最开始 DuckDB 采用 pull-based 的执行引擎，每个算子都实现了 `GetChunk` 算子，非常经典的 valcano 模型。在这个模型中，单线程执行是非常自然的，多线程并行的能力不是很好。

（duckdb团队的转变的心路历程：https://github.com/duckdb/duckdb/issues/1583）

这种运算符的一个简单示例是投影：

```cpp
void PhysicalProjection::GetChunkInternal(ExecutionContext &context, DataChunk &chunk, PhysicalOperatorState *state_p) {
    auto state = reinterpret_cast<PhysicalProjectionState *>(state_p);
﻿
    // get the next chunk from the child
    children[0]->GetChunk(context, state->child_chunk, state->child_state.get());
    if (state->child_chunk.size() == 0) {
        return;
    }
﻿
    state->executor.Execute(state->child_chunk, chunk);
}
```

但是这种架构在引入pipeline后，不再需要“从根节点拉取”的行为。相反，我们希望单独执行各个流水线。

﻿

Pull 模型下执行整个 Query 就是拉这颗树的树根从而驱动整个执行过程，很函数式。不过 Pull 模式也有几个明显的缺点，导致它与 Pipeline 并行不那么合拍。个人感觉最主要的因素还是调度的可控性方面，Query 执行的控制流掌握在算子手中，调度器想要拆开这棵树做并行就相对无从下手，想并行就得在算子内部写并行逻辑，就更破坏封装了。反观 Push-based 模型下，每个算子不会直接调用下游的迭代器来获取数据，而是在回调函数中接收上游的数据。

﻿

更重要的是，算子树会转换成为诸多 Pipeline 构成的物理计划，将 Pipeline 作为调度的单位，每个 Pipeline 内部更是可以并行执行，从而将并行的潜力完全的释放出来。

﻿

***\*Push 模型简化图\****

```cpp
idx_t index = 0;
vector<DataChunk> intermediates;
vector<unique_ptr<PhysicalOperatorState>> states;
// initialize intermediate structures and states
intermediates.resize(pipeline_nodes.size());
states.resize(pipeline_nodes.size());
for(idx_t i = 0; i < pipeline_nodes.size(); i++) {
    intermediates[i].Initialize(pipeline_nodes[i]->return_type);
    states[i] = pipeline_nodes[i]->GetOperatorState(context);
}
﻿
while(true) {
    pipeline_nodes[0]->Scan(context, states[0].get(), partition_state, intermediates[0]);
    if (intermediates[0].size() == 0) {
        // empty result from scan: bail
        break;
    }
    bool finished = true;
    for(idx_t i = 1; i < pipeline_nodes.size() - 1; i++) {
        pipeline_nodes[i]->Execute(context, states[i].get(), intermediates[i - 1], intermediates[i]);
        if (intermediates[i].size() == 0) {
            // everything was filtered: move to next node from scan
            finished = false;
            break;
        }
    }
    if (finished) {
        // finished pipeline: sink into operator
        auto &sink = pipeline_nodes.back();
        sink->Sink(context, global_state, sink_state, intermediates[intermediates.size() - 1]);
    }
}
```

﻿

# 2. Pipeline构造算子

 duckdb 有三类算子，分别是`Source`，`Operator`  和 `Sink`。其中source 和 sink 算子能够感知到全局状态以及并行，中间的每个 `Operator` 算子都是不感知并行，只是做计算。

﻿

## Source 算子

一类特殊的物理执行算子（Physical Operator），它们位于查询执行计划的最底层，负责执行将***\*数据导入内存\****的操作。典型的如seqscan

```sql
explain select * from t1;
100% ▕██████████████████████████████████████▏ (00:01:22.01 elapsed)

┌─────────────────────────────┐
│┌───────────────────────────┐│
││       Physical Plan       ││
│└───────────────────────────┘│
└─────────────────────────────┘
┌───────────────────────────┐
│         SEQ_SCAN          │
│    ────────────────────   │
│         Table: t1         │
│   Type: Sequential Scan   │
│                           │
│        Projections:       │
│             id            │
│            age            │
│                           │
│          ~3 rows          │
└───────────────────────────┘
```

调用堆栈如下：

```c++
|-->Executor::InitializeInternal()  //执行器的入口
|		|-->MetaPipeline::Build() 		//metapipeline是个基类,主要对用各个子类的buildPipelines()方法
|		|		|-->PhysicalResultCollector::BuildPipelines() //对应plan的pipleline方法
```

基类opeartor算子`PhysicalOperator`, 其他算子都继承与它，在判断是否是Source，取决于子类方法。其接口函数如下

```c++
// Source interface
	virtual unique_ptr<LocalSourceState> GetLocalSourceState(ExecutionContext &context,
	                                                         GlobalSourceState &gstate) const;
	virtual unique_ptr<GlobalSourceState> GetGlobalSourceState(ClientContext &context) const;
	virtual SourceResultType GetData(ExecutionContext &context, DataChunk &chunk, OperatorSourceInput &input) const;

	virtual OperatorPartitionData GetPartitionData(ExecutionContext &context, DataChunk &chunk,
	                                               GlobalSourceState &gstate, LocalSourceState &lstate,
	                                               const OperatorPartitionInfo &partition_info) const;

	virtual bool IsSource() const {
		return false;
	}
```

##  Sink 算子

Sink 算子是 DuckDB 中实现复杂 SQL 功能的关键，它会安排在每个流水线的末尾，Sink 在消费完所有上游的数据后，往往也可以作为下游 Pipeline 的 Source 去产出数据。并在pipeline中承担Pipeline breaker的作用。常用类型如下

| **Sink 算子 (及其相关阻塞算子)** | **对应的 SQL/功能**                            | **Sink 阶段的主要任务**                                      |
| -------------------------------- | ---------------------------------------------- | ------------------------------------------------------------ |
| **`Sort`**                       | **`ORDER BY`**                                 | 线程本地生成**有序运行块 (sorted runs)**，累积所有数据以便最终合并。 |
| **`Aggregate`**                  | **`GROUP BY`** 和聚合函数（如 `SUM`, `COUNT`） | 线程本地进行部分聚合计算。                                   |
| **`HashJoin` 的 Build Side**     | **`JOIN`** 操作                                | 接收 Build 表（较小的表）的数据，并在内存中构建**哈希表**以供 Probe Side 使用。 |
| **`Window`**                     | **`OVER (PARTITION BY ...)`**                  | 接收数据并按分区键进行分区，以便在每个分区内执行窗口函数。   |
| **`Result` / `Materialize`**     | **最终结果集**                                 | 这是查询管道中最顶层的 Sink。它接收所有处理后的数据，并将其**物化**为最终结果集，准备返回给用户。 |

其接口函数如下

```c++
virtual SinkResultType Sink(ExecutionContext &context, DataChunk &chunk, OperatorSinkInput &input) const;
virtual SinkCombineResultType Combine(ExecutionContext &context, OperatorSinkCombineInput &input) const;
virtual SinkFinalizeType Finalize(Pipeline &pipeline, Event &event, ClientContext &context,
	                                  OperatorSinkFinalizeInput &input) const;
```

每个线程有一个 LocalSinkState(基类)，在消费完数据后，本地线程 Combine 一次，最后再跑最重的 Finalize 过程将多个 LocalSinkState 的中间结果合并。比如做 Hash Aggregation，就相当于每个线程可以弄一个自己的小哈希表，这样在 Finalize 之前没有内存共享。



## Pipeline的构造

![image-20251027193437958](/Users/yangjinyin/Library/Application Support/typora-user-images/image-20251027193437958.png)

其原理来源于一篇paper 《[Morsel-Driven Parallelism: A NUMA-Aware Query Evaluation Framework for the Many-Core Age](https://link.zhihu.com/?target=https%3A//15721.courses.cs.cmu.edu/spring2016/papers/p743-leis.pdf)》

大部分算子的BuildPipelines()都采用基类方法, 如下：

```c++
void PhysicalOperator::BuildPipelines(Pipeline &current, MetaPipeline &meta_pipeline) {
	op_state.reset();

	auto &state = meta_pipeline.GetState();
	if (IsSink()) {
		// operator is a sink, build a pipeline
		sink_state.reset();
		D_ASSERT(children.size() == 1);

		// single operator: the operator becomes the data source of the current pipeline
		state.SetPipelineSource(current, this);

		// we create a new pipeline starting from the child
		auto child_meta_pipeline = meta_pipeline.CreateChildMetaPipeline(current, this);
		child_meta_pipeline->Build(children[0].get());
	} else {
		// operator is not a sink! recurse in children
		if (children.empty()) {
			// source
			state.SetPipelineSource(current, this);
		} else {
			if (children.size() != 1) {
				throw InternalException("Operator not supported in BuildPipelines");
			}
			state.AddPipelineOperator(current, this);
      //递归构造 Pipeline
			children[0]->BuildPipelines(current, meta_pipeline);
		}
	}
}
```

三个分支逻辑：

1. 如果当前算子是 IsSink()，则将自身作为当前 Pipeline 的 Source，并通过 CreateChildMetaPipeline 创建一个新的 MetaPipeline 并递归执行 Build()，将这里作为 Pipeline Breaker 开启新的 Pipeline；Pipeline 的 sink 会先被确定下来（要么是整个物理执行计划的根节点，要么是上一个 Pipeline 的 source 节点）
2. 如果当前算子是 Source，则直接将自身作为当前 Pipeline 的 Source；
3. 如果当前算子是中间的无状态 Operator，则通过 state.AddPipelineOperator 将自身追加到 Pipeline 末尾，最后按下一个算子递归执行 BuildPipelines。



## HashJoin的pipeline构造

```
D explain select * from t1,t where t.id = t1.id;
100% ▕██████████████████████████████████████▏ (00:00:30.06 elapsed)

┌─────────────────────────────┐
│┌───────────────────────────┐│
││       Physical Plan       ││
│└───────────────────────────┘│
└─────────────────────────────┘
┌───────────────────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             id            │
│            age            │
│             id            │
│                           │
│          ~3 rows          │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             #2            │
│__internal_decompress_integ│
│     ral_integer(#1, 1)    │
│             #0            │
│__internal_decompress_integ│
│     ral_integer(#4, 2)    │
│__internal_decompress_integ│
│     ral_integer(#3, 1)    │
│                           │
│          ~3 rows          │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         HASH_JOIN         │
│    ────────────────────   │
│      Join Type: INNER     │
│    Conditions: id = id    ├──────────────┐
│                           │              │
│          ~3 rows          │              │
└─────────────┬─────────────┘              │
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         PROJECTION        ││         PROJECTION        │
│    ────────────────────   ││    ────────────────────   │
│            NULL           ││            NULL           │
│             #0            ││             #1            │
│            NULL           ││            NULL           │
│                           ││             #0            │
│                           ││            NULL           │
│                           ││                           │
│          ~4 rows          ││          ~3 rows          │
└─────────────┬─────────────┘└─────────────┬─────────────┘
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│         SEQ_SCAN          ││         SEQ_SCAN          │
│    ────────────────────   ││    ────────────────────   │
│          Table: t         ││         Table: t1         │
│   Type: Sequential Scan   ││   Type: Sequential Scan   │
│      Projections: id      ││                           │
│                           ││        Projections:       │
│                           ││             id            │
│                           ││            age            │
│                           ││                           │
│                           ││       Filters: id<=4      │
│                           ││                           │
│          ~4 rows          ││          ~3 rows          │
└───────────────────────────┘└───────────────────────────┘
```

```c++
void PhysicalJoin::BuildJoinPipelines(Pipeline &current, MetaPipeline &meta_pipeline, 
                                     PhysicalOperator &op, bool build_rhs) {
  // 1. 重置操作符状态
  op.op_state.reset();
  op.sink_state.reset();

  // 2. 将当前操作符添加到probe pipeline
  auto &state = meta_pipeline.GetState();
  state.AddPipelineOperator(current, op);

  // 3. 保存已构建的pipeline用于设置依赖
  vector<shared_ptr<Pipeline>> pipelines_so_far;
  meta_pipeline.GetPipelines(pipelines_so_far, false);
  auto &last_pipeline = *pipelines_so_far.back();

  // 4. 构建build pipeline(右侧) 
  vector<shared_ptr<Pipeline>> dependencies;
  optional_ptr<MetaPipeline> last_child_ptr;
  if (build_rhs) {
    // 创建build侧的child MetaPipeline
    auto &child_meta_pipeline = meta_pipeline.CreateChildMetaPipeline(
        current, op, MetaPipelineType::JOIN_BUILD);
    
    // 递归构建右侧child pipeline
    child_meta_pipeline.Build(op.children[1]);
    
    // 如果右侧可以饱和所有线程,则设置递归依赖
    if (op.children[1].get().CanSaturateThreads(current.GetClientContext())) {
      child_meta_pipeline.GetPipelines(dependencies, false);
      last_child_ptr = meta_pipeline.GetLastChild();
    }
  }

  // 5. 构建probe pipeline(左侧)
  op.children[0].get().BuildPipelines(current, meta_pipeline);

  // 6. 设置依赖关系
  if (last_child_ptr) {
    meta_pipeline.AddRecursiveDependencies(dependencies, *last_child_ptr);
  }

  // 7. 处理特殊连接类型
  switch (op.type) {
    case PhysicalOperatorType::POSITIONAL_JOIN:
      // Positional join需要创建子pipeline
      meta_pipeline.CreateChildPipeline(current, op, last_pipeline);
      return;
    case PhysicalOperatorType::CROSS_PRODUCT:
      return;
    default:
      break;
  }

  // 8. 对RIGHT/OUTER JOIN创建额外的源pipeline
  if (op.Cast<PhysicalJoin>().IsSource()) {
    meta_pipeline.CreateChildPipeline(current, op, last_pipeline); 
  }
}
```



# 3. 执行框架

## 3.1 启动阶段

DuckDB 启动时会创建一个全局的 TaskScheduler，启动 ncore-1个后台线程。这些后台线程启动后会不停地从位于 TaskScheduler 的 Task 队列中取出和执行 Task。DuckDB 通过这个后台线程池和公共 Task 队列完成了 Query 的并发执行。

```c++
|-->DuckDB::DuckDB()
|		|-->DatabaseInstance::Initialize() //数据库实例初始化
|		|		|-->1. Configure() //配置初始化
|		|		|-->2. make_uniq<DatabaseFileSystem> //创建文件系统
|		|		|-->3. make_uniq<DatabaseManager> //创建db 管理器
|		|		|-->4. make_uniq<StandardBufferManager> //创建buffer-pool管理器
|		|		|-->5. scheduler = make_uniq<TaskScheduler> //创建任务调度器
|		|		|-->....
|		|		|-->scheduler->SetThreads() //设置线程数，根据当前系统有多少core，创建n-1个后台线程
|		|		|-->TaskScheduler::RelaunchThreads() //启动后台线程
|		|		|		|-->unique_ptr<thread> worker_thread; //创建线程
|		|		|		|-->worker_thread = make_uniq<thread>(ThreadExecuteTasks, this, marker.get())//启动工作线程
|		|		|		|		|-->TaskScheduler::ExecuteForever() //线程执行任务
|		|		|		|		|		|-->queue->Dequeue(task)//从task队列里取出task
|		|		|		|		|		|-->task->Execute() //执行不同的task任务
|		|		|		|-->SetThreadAffinity() //绑核
|		|		|		|-->threads.push_back(std::move(thread_wrapper));//加入线程池
```

调度任务的核心函数`ExecuteForever`

```c++
void TaskScheduler::ExecuteForever(atomic<bool> *marker) {
#ifndef DUCKDB_NO_THREADS
  // 1. 常量定义
  static constexpr const int64_t INITIAL_FLUSH_WAIT = 500000; // 初始等待时间0.5秒
  
  // 2. 获取配置
  auto &config = DBConfig::GetConfig(db);
  shared_ptr<Task> task;
  
  // 3. 主循环 - 直到marker为false
  while (*marker) {
    // 3.1 处理内存分配器flush
    if (!Allocator::SupportsFlush()) {
      // 不支持flush - 直接等待任务
      queue->semaphore.wait();
    } else if (!queue->semaphore.wait(INITIAL_FLUSH_WAIT)) {
      // 支持flush且等待超时 - 执行flush
      Allocator::ThreadFlush(allocator_background_threads, 
                           allocator_flush_threshold,
                           requested_thread_count);
      
      // 3.2 处理内存衰减
      auto decay_delay = Allocator::DecayDelay();
      if (!decay_delay.IsValid()) {
        queue->semaphore.wait();
      } else {
        // 计算总等待时间并等待
        auto total_wait = decay_delay.GetIndex() * 1000000 - INITIAL_FLUSH_WAIT;
        if (!queue->semaphore.wait(total_wait)) {
          // 线程空闲整个衰减期
          Allocator::ThreadIdle();
          queue->semaphore.wait();
        }
      }
    }

    // 3.3 获取并执行任务  
    if (queue->Dequeue(task)) {
      // 根据配置确定执行模式
      auto process_mode = config.options.scheduler_process_partial ? 
                         TaskExecutionMode::PROCESS_PARTIAL : 
                         TaskExecutionMode::PROCESS_ALL;
      
      // 执行任务
      auto execute_result = task->Execute(process_mode);

      // 3.4 处理执行结果
      switch (execute_result) {
        case TaskExecutionResult::TASK_FINISHED:
        case TaskExecutionResult::TASK_ERROR:
          // 任务完成或出错 - 清理
          task.reset();
          break;
          
        case TaskExecutionResult::TASK_NOT_FINISHED: 
          // 任务未完成 - 立即重新调度
          auto &token = *task->token;
          queue->Enqueue(token, std::move(task));
          break;
          
        case TaskExecutionResult::TASK_BLOCKED:
          // 任务阻塞 - 取消调度
          task->Deschedule();
          task.reset();
          break;
      }
    } else if (queue->GetTasksInQueue() > 0) {
      // 获取失败但队列非空 - 重试
      queue->semaphore.signal(1);
    }
  }

  // 4. 线程退出前刷新内存
  if (Allocator::SupportsFlush()) {
    Allocator::ThreadFlush(allocator_background_threads, 0, 
                          requested_thread_count);
    Allocator::ThreadIdle();
  }
#else
  throw NotImplementedException("No threads support!");
#endif
}
```



## 3.2 Pipeline 入队列流程

由 PhysicalOperator tree 构建出来的Pipeline集合，每个 Pipeline 代表了物理执行计划中一段连续的 PhysicalOperator 算子，由 source、operators 和 sink 构成。当且仅当 Pipeline 的所有 dependency 都执行完后，该 Pipeline 才可被执行。Pipeline 的 sink 代表了需要消费掉所有输入数据才能对外返回结果的 PhysicalOperator。

在实现过程中，通过 Event 来生成和调度对应的 ExecutorTask。具体流程如下

```c++
|-->Executor::InitializeInternal()
|		|-->1. root_pipeline->Build(*physical_plan) //递归先生成所有的pipeline
|		|-->2. root_pipeline->GetMetaPipelines() //收集所有的metapipelines
|		|-->3. Executor::ScheduleEvents() //加入调度队列
|		|		|-->Executor::ScheduleEventsInternal()
|		|		|		|-->3.1 Executor::SchedulePipeline()//为每一个pipeline创建一系列的event,并添加这些event上下依赖关系
|		|		|		|-->3.2 event->Schedule()//根据不同event类型，调用不同的函数
|		|		|		|		|-->case: PipelineEvent::Schedule()//PipelineEvent 类型
|		|		|		|		|		|-->Pipeline::Schedule() 
|		|		|		|		|		|		|-->Pipeline::ScheduleParallel() //并行扫描
|		|		|		|		|		|		|		|-->Pipeline::LaunchScanTasks()
|		|		|		|		|		|		|		|		|-->Event::SetTasks()
|		|		|		|		|		|		|		|		|		|-->TaskScheduler::ScheduleTasks()
|		|		|		|		|		|		|		|		|		|		|-->queue->EnqueueBulk(producer, tasks);//批量入task队列 
|		|		|		|		|		|		|-->Pipeline::ScheduleSequentialTask()//如果不能并行的，则串行执行
|		|		|		|		|		|		|		|-->Event::SetTasks()//生成task并入列
|		|		|		|		|-->case: //PipelineInitializeEvent PipelinePrepareFinishEvent PipelineFinishEvent 
|		|		|		|		|		|-->Event::SetTasks()//生成task并入列
```



## 3.3 执行阶段

ExecutorTask 中的 Pipeline 是以 push 的方式执行的：先从 Pipeline 的 source 获取一批数据，然后将该批数据依次的通过所有中间的 operators 计算，最终由 sink 完成这一批初始数据的最终计算。典型的 sink 比如构造 hash table：当前 Pipeline 的所有 ExecutorTask 执行完后，最终的 hash table 才构造好，才能用来 probe 产生结果。

eg: 最简单的select * from t1 举例

```c++
|-->TaskScheduler::ExecuteForever()
|		|-->1. PipelineInitializeTask::ExecuteTask()//先执行initializetask
|		|-->2. PipelineTask::ExecuteTask() 
|		|		|-->PipelineExecutor::Execute()//对应各种operator task,并且控制sink，combine流程
|		|		|		|-->PipelineExecutor::FetchFromSource()//取数据
|		|		|		|		|-->pipeline.source->GetData() //跟source算子取数据
|		|-->3. PipelinePreFinishTask::ExecuteTask() //preparefinish event
|		|-->4. PipelineFinishTask::ExecuteTask() //finish event
```

PipelineExecutor::Execute() 与PipelineExecutor::ExecutePushInternal() 是pipeline控制流最重要的部分。还得细看

### 3.3.1 PipelineExecutor::Execute()

### 3.3.2 PipelineExecutor::ExecutePushInternal()