

# 0  基础知识

![在这里插入图片描述](https://i-blog.csdnimg.cn/direct/35db1bf22b5b4c87a1487cabcfe2617c.png)



## pthread线程库

几乎所有linux平台都是默认自带这个pthread线程库的，默认一般在 `/lib64/libpthread.so.0`

### 创建

```c++
#include <pthread.h>

int pthread_create(pthread_t *thread, const pthread_attr_t *attr,
                   void *(*start_routine)(void *), void *arg);

```

参数说明

- `pthread_t *thread`：指向 `pthread_t` 类型的变量的指针，用于存储新创建线程的 ID。
- `const pthread_attr_t *attr`：指向线程属性对象的指针，可以为 `NULL`，表示使用默认属性。可以通过 `pthread_attr_init()` 等函数来初始化和设置线程属性。
- `void *(*start_routine)(void *)`：指向线程执行函数的指针。该函数接受一个 `void*` 类型的参数，并返回一个 `void*` 类型的值。
- `void *arg`：传递给线程函数的参数，可以是指向任何类型的指针。在线程函数中需要将其转换回合适的类型。



### 线程等待

```c++
#include <pthread.h>

int pthread_join(pthread_t thread, void **retval);
```

参数

1. **`thread`**: 要等待的线程的标识符，即由 `pthread_create` 创建线程时返回的 `pthread_t` 类型的值。
2. **`retval`**: 指向指针的指针，用于接收线程的返回值。如果不需要获取返回值，可以将其设置为 `NULL`。



### 线程终止

```c++
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>

// 线程函数
void* thread_function(void* arg) {
    int *result = malloc(sizeof(int));
    *result = 42; // 计算结果
    printf("Thread is running...\n");
    pthread_exit(result); // 终止线程，并返回结果
}

int main() {
    pthread_t thread;
    void *retval;

    // 创建线程
    if (pthread_create(&thread, NULL, thread_function, NULL) != 0) {
        perror("Failed to create thread");
        return 1;
    }

    // 等待线程结束
    pthread_join(thread, &retval);
    printf("Thread terminated with value: %d\n", *((int*)retval));
    free(retval); // 释放返回值内存

    return 0;
}
```



## C++11中的多线程

c++11中也支持了多线程，c++11支持的多线程的底层是对pthread线程库进行的封装，而pthread线程库的底层是对linux轻量级进程的系统调用诸如clone等进行的封装



































# 1：pg中使用CAS实现无锁队列

- ProcArrayLock    
  - 优化前：事务提交清理proc的xid，所有进程争抢ProcArrayLock（PG的锁机制会用sem排队）。
  - 优化后：第一个向队列加入元素的proc为leader，后续的proc使用cas将要做的加入队列，由leader统一做。





```c
while (true)
	{
		pg_atomic_write_u32(&proc->procArrayGroupNext, nextidx);

		if (pg_atomic_compare_exchange_u32(&procglobal->procArrayGroupFirst,
										   &nextidx,
										   (uint32) pgprocno)) 
			break;
	}

//x86
static inline bool
pg_atomic_compare_exchange_u32_impl(volatile pg_atomic_uint32 *ptr,
									uint32 *expected, uint32 newval)
{
	char	ret;

	/*
	 * Perform cmpxchg and use the zero flag which it implicitly sets when
	 * equal to measure the success.
	 */
	__asm__ __volatile__(
		"	lock				\n"
		"	cmpxchgl	%4,%5	\n"
		"   setz		%2		\n"
:		"=a" (*expected), "=m"(ptr->value), "=q" (ret)
:		"a" (*expected), "r" (newval), "m"(ptr->value)
:		"memory", "cc");
	return (bool) ret;
}

```

