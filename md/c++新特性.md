# I.  C++11  14新特性

## 1. **自动类型推导**

- `auto` 关键字：编译器自动推导变量类型

- `decltype`：获取表达式的类型

  ```c++
  int i = 4;    
  decltype(i) a; //推导结果为int。a的类型为int
  ```

## 2. **智能指针**

- `std::unique_ptr`：独占所有权的智能指针

​	**唯一所有权**：资源只能由一个`unique_ptr`拥有

​	**不可复制**，只能移动（move）

​	**使用场景**：适合用于表示独占的资源管理，例如在类中持有不应该被共享的资源

```c++
#include <memory>

// 创建unique_ptr
std::unique_ptr<int> p1 = std::make_unique<int>(42);
std::unique_ptr<int[]> p2 = std::make_unique<int[]>(10);  // 数组版本

// 移动所有权
std::unique_ptr<int> p3 = std::move(p1);  // p1现在为nullptr
```

- `std::shared_ptr`：共享所有权的智能指针

  **共享所有权**：多个`shared_ptr`可以指向同一对象

  **引用计数**：跟踪有多少个`shared_ptr`指向对象

  **当引用计数为0时自动删除对象**

  ```c++
  #include <memory>
  
  std::shared_ptr<int> ptr1(new int(5)); // 创建 shared_ptr
  std::shared_ptr<int> ptr2 = ptr1; // 共享所有权，引用计数增加
  // ptr1 和 ptr2 都指向同一块内存
  ```

- `std::weak_ptr`：弱引用智能指针

​	**不增加引用计数**

​	**不拥有对象所有权**

​	**用于解决`shared_ptr`的循环引用问题**

```c++
#include <memory>

auto shared = std::make_shared<int>(42);
std::weak_ptr<int> weak = shared;  // 创建weak_ptr，引用计数不变

// 使用时检查对象是否还存在
if (auto temp = weak.lock()) {  // 尝试获取shared_ptr
    std::cout << "Value: " << *temp << "\n";
} else {
    std::cout << "Object has been destroyed\n";
}

// 检查是否过期
if (weak.expired()) {
    std::cout << "Object no longer exists\n";
}
```



## 3. **右值引用与移动语义**

- 右值引用 `&&`

  右值引用允许将资源从一个对象"移动"到另一个对象，而不是进行深拷贝

  ```c++
  int a = 5;          // a是左值（有名字，有地址）
  int& lref = a;      // 左值引用
  
  int&& rref = 5;     // 右值引用绑定到字面量
  int&& rref2 = a + 3; // 右值引用绑定到临时结果
  ```

- 移动构造函数和移动赋值运算符

- `std::move()` 函数

## 4. **Lambda 表达式**

### 基本语法：

```c++
[capture](parameters) -> return_type {
    // function body
}
```

1. **Capture（捕获列表）**： 捕获外部变量的方式。它可以是：
   - `[]`：不捕获任何外部变量。
   - `[x, y]`：捕获 `x` 和 `y`，可以在 lambda 中使用它们。
   - `[=]`：按值捕获所有外部变量。
   - `[&]`：按引用捕获所有外部变量。
   - `[this]`：捕获当前对象的指针。
2. **Parameters（参数列表）**： 和普通函数一样，定义 lambda 函数的输入参数。也可以省略，表示没有参数。
3. **Return Type（返回类型）**： 可选，表示 lambda 表达式的返回类型。如果省略，编译器会根据函数体自动推断。
4. **Function Body（函数体）**： Lambda 表达式的函数体，定义了执行的具体内容。

## 5. **范围for循环**

```c++
for (auto& item : container) { }
```

## 6. **nullptr**

- 替代 `NULL`，类型安全的空指针常量

## 7. **强类型枚举**

```c++
enum class Color { Red, Green, Blue };
```

## 8. **委托构造函数**

- 构造函数可以调用同一类的其他构造函数

## 9. **列表初始化**

```
vector<int> v = {1, 2, 3, 4};
```

## 10. **constexpr**

- 编译期常量表达式：这意味着编译时计算其值，而不是在运行时。这有助于提高性能，因为编译器在生成代码时可以直接使用这些常量值

  ```c++
  constexpr int square(int x) {
      return x * x;
  }
  
  constexpr int result = square(5); // result 在编译时计算为 25
  ```

## 11. **变参模板**

​	变参模板的基本语法使用三个点（`...`）表示，可以应用于类型参数和非类型参数

```c++
#include <iostream>

// 一个简单的求和函数
template<typename... Args>
int sum(Args... args) {
    return (args + ...); // C++17 的折叠表达式
}

int main() {
    std::cout << sum(1, 2, 3, 4) << std::endl; // 输出: 10
    return 0;
}
```



## 12. **线程支持库**

- `std::thread`
- `std::mutex`
- `std::condition_variable`
- `std::atomic`

###  lock_guard

互斥锁，保护临界区，相比 `unique_lock` 更轻量，**始终优先考虑 `lock_guard`**

```c++
#include <iostream>
#include <mutex>
#include <thread>

std::mutex mtx;
int shared_data = 0;

void increment() {
    // lock_guard 在构造时自动锁定互斥量
    std::lock_guard<std::mutex> lock(mtx);
    
    // 临界区开始
    for (int i = 0; i < 1000; ++i) {
        ++shared_data;
    }
    // 临界区结束
    // lock_guard 析构时自动解锁互斥量
}
int main() {
	std::thread t1(increment);
	std::thread t2(increment);

	t1.join();
	t2.join();

	return 0;
}
```

### unique_lock

**独占锁**，提供了比传统的锁操作更灵活和安全的方式。它可以与多种类型的互斥量一起使用，如 `std::mutex`, `std::timed_mutex`, `std::recursive_mutex` 等

**常与条件变量一起使用，以实现线程间的同步**

```c++
#include <iostream>
#include <thread>
#include <mutex>
#include <condition_variable>

std::mutex mtx;
std::condition_variable cv;
bool ready = false;

void worker() {
    std::unique_lock<std::mutex> lock(mtx);
    cv.wait(lock, [] { return ready; }); // 等待直到 ready 为 true
    std::cout << "Worker thread proceeding..." << std::endl;
}

int main() {
    std::thread t(worker);

    // 模拟一些工作
    std::this_thread::sleep_for(std::chrono::seconds(1));

    {
        std::lock_guard<std::mutex> lock(mtx); // 使用 lock_guard 保护 ready
        ready = true; // 设置 ready 为 true
    }

    cv.notify_one(); // 通知等待的线程

    t.join();
    return 0;
}
```

### shared_lock

**共享互斥量**，允许多个线程同时读取共享数据，但在写入数据时仍然保证互斥

```c++
#include <iostream>
#include <mutex>
#include <shared_mutex>
#include <thread>

std::shared_mutex sh_mtx;
int shared_data = 0;

void read_data() {
	std::shared_lock<std::shared_mutex> lock(sh_mtx);
	std::cout << "Read shared_data: " << shared_data << std::endl;
}

void write_data() {
	std::unique_lock<std::shared_mutex> lock(sh_mtx);
	++shared_data;
	std::cout << "Incremented shared_data: " << shared_data << std::endl;
}

int main() {
	std::thread t1(read_data);
	std::thread t2(write_data);
	std::thread t3(read_data);

	t1.join();
	t2.join();
	t3.join();

	return 0;
}
```

### scoped_lock

这是 C++17 引入的一个新锁，用于同时锁定多个互斥量，以避免死锁

```c++
#include <iostream>
#include <mutex>
#include <thread>

std::mutex mtx1;
std::mutex mtx2;
int shared_data1 = 0;
int shared_data2 = 0;

void increment_both() {
    std::scoped_lock lock(mtx1, mtx2);
    ++shared_data1;
    ++shared_data2;
    std::cout << "Incremented shared_data1: " << shared_data1 << ", shared_data2: " << shared_data2 << std::endl;
}

int main() {
    std::thread t1(increment_both);
    std::thread t2(increment_both);

    t1.join();
    t2.join();

    return 0;
}
```



## 13. **其他重要特性**

- `static_assert`：编译期断言

- `final` 和 `override` 关键字

- `default` 和 `delete` 函数

- `noexcept` 异常说明符

- 原始字符串字面量

- `std::array` 容器

- `std::unordered_map/set`（哈希表）

- `std::tuple`

  提供了一种灵活的方法来将多个相关值组合在一起，并允许通过索引访问。

  ```c++
  #include <iostream>
  #include <tuple>
  
  int main() {
      auto myTuple = std::make_tuple(42, 3.14, "hello");
  
      std::cout << std::get<0>(myTuple) << std::endl; // 输出: 42
      std::cout << std::get<1>(myTuple) << std::endl; // 输出: 3.14
      std::cout << std::get<2>(myTuple) << std::endl; // 输出: hello
  
      return 0;
  }
  ```

- `std::function` 和 `std::bind`

​	它们在函数对象和回调机制中起着关键作用

```c++
#include <iostream>
#include <functional>

void multiply(int a, int b) {
    std::cout << "Product: " << a * b << std::endl;
}

int main() {
    // 绑定第一个参数
    auto boundMultiply = std::bind(multiply, 3, std::placeholders::_1);

    // 将绑定的可调用对象赋值给 std::function
    std::function<void(int)> func = boundMultiply;

    // 只需提供第二个参数
    func(4); // 输出: Product: 12

    return 0;
}
```

## 14. **std::exchange**

它用于交换两个值，并返回被交换的旧值

```c++
int old = std::exchange(x, 42);
```



# II.  显式转换

## static_cast

是一种类型安全的转换，适用于具有明确转换关系的类型（如基本类型、指针类型和引用类型之间的转换）

```c++
#include <iostream>

class Base {};
class Derived : public Base {};

int main() {
    Derived d;
    Base* b = static_cast<Base*>(&d); // 从派生类到基类的安全转换
    return 0;
}
```

## dynamic_cast

主要用于处理多态和类层次结构中的安全转换。它通常用于将基类指针或引用转换为派生类指针或引用，并在运行时检查类型安全

```c++
#include <iostream>
#include <typeinfo>

class Base {
    virtual void func() {}
};

class Derived : public Base {
    void func() override {}
};

int main() {
    Base* b = new Derived();
    Derived* d = dynamic_cast<Derived*>(b); // 安全转换

    if (d) {
        std::cout << "成功转换为 Derived 类型。" << std::endl;
    } else {
        std::cout << "转换失败。" << std::endl;
    }

    delete b; // 不要忘记释放内存
    return 0;
}
```

## const_cast

用于移除对象的 const 或 volatile 限定符

```c++
void printValue(const int* ptr) {
    int* modifiablePtr = const_cast<int*>(ptr);
    *modifiablePtr = 100; // 修改 const 数据，可能导致未定义行为
}
```

## reinterpret_cast

最强大且最危险的类型转换，允许在不考虑类型安全的情况下重新解释一个指针类型。

可以用来将一个指针类型转换为与之完全不同的类型。例如，将 `void*` 转换为 `int*`，或者将一个指向某种类型的指针转换为另一个类型的指针

```c++
void* void_ptr = &x;
int* int_ptr = reinterpret_cast<int*>(void_ptr);  // 将 void* 转换为 int*
```





# III. C++17 新特性

## [[nodiscard]]属性

用于强调函数的返回值不会被丢弃，否则会出现编译器警告

## [[maybe_unused]]属性

## std::optional

用于表示可能缺失的值。它可以包含一个有效的值或不包含任何值（即空状态）

```c++
std::optional<std::string> findName(int id) {
    if (id == 1) {
        return "Alice"; // 返回有效值
    } else {
        return std::nullopt; // 返回空状态
    }
}
```

## std::string_view

提供了一种不拥有字符串内容的方式来引用字符串。它通常用于函数参数，以避免不必要的字符串拷贝，并提高性能

```c++
std::string s = "Hello, world!";
std::string_view sv = s.substr(0, 5); // 创建字符串视图
```



##  **并行算法**

C++17引入了许多并行版本的标准库中的算法。这些算法可以并行执行，因此在多核系统上可能会带来显著的性能提升。

### std::execution策略

并行算法通过`std::execution`策略参数来指定执行方式。C++17定义了以下三种执行策略：

1. `std::execution::seq`：顺序执行策略，与传统的STL算法相同，不涉及并行计算。
2. `std::execution::par`：并行执行策略，允许算法在多个线程上并行执行。
3. `std::execution::par_unseq`：并行+向量化执行策略，允许算法在多个线程上并行执行，并充分利用CPU的向量化能力（如SIMD指令集

```c++
#include <algorithm>
#include <vector>
#include <execution>
int main() {
    std::vector<int> v = {1, 2, 3, 4, 5};
    std::sort(std::execution::par, v.begin(), v.end());
}
```





# IV. C++20新特性

## 协程

## **概念（Concepts）**

## **范围（Ranges）库**

## 模块（Modules）

```c++
//1. 定义模块
export module math; // 声明模块

export int add(int a, int b) {
    return a + b;
}

export int subtract(int a, int b) {
    return a - b;
}

//2. 导入模块
import math; // 导入模块

#include <iostream>

int main() {
    std::cout << "5 + 3 = " << add(5, 3) << std::endl;
    std::cout << "5 - 3 = " << subtract(5, 3) << std::endl;
    return 0;
}
```



# V. STL

**1.map：key-value存储的容器，key 唯一，自动排序；红黑树实现**

**2.unordered_map:hash表进行存储数据;其操作跟map类似。key唯一，元素无需。hash表实现。**

**3.set ：自动去重，自动排序。查重快，插入和删除慢**

**4.unordered_set : 元素唯一，无序。查找删除插入快。使用hash表实现 会占用更多内存**

**6.list：双向链表，不支持快速随机访问。快速插入，内存效率高**

**5.vector：可变大小数组**     

