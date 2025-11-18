# 1： lambda 表达式（匿名函数）

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



# 2. reinterpret_cast

可以用来将一个指针类型转换为与之完全不同的类型。例如，将 `void*` 转换为 `int*`，或者将一个指向某种类型的指针转换为另一个类型的指针

```c++
void* void_ptr = &x;
int* int_ptr = reinterpret_cast<int*>(void_ptr);  // 将 void* 转换为 int*
```

