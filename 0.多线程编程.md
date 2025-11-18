# 一：pg中使用CAS实现无锁队列

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

