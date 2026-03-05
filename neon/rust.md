# 一： 基础入门

## 1. 变量定义

```rust
let x = 6 ； //rust 默认变量不可变

let mut x = 6；//加上mut 后变量可变

let _x = 5;  // 使用下划线开头忽略未使用的变量
```



## 2.变量解构

```rust
let (a, mut b): (bool,bool) = (true, false); // a = true,不可变; b = false，可变

```



## 3.基本类型

```rust
数值类型：
  有符号整数：i8， i16, i32, i64, i128, isize
  无符号整数：u8， u16, u32, u64, u128, usize
  浮点数：f32（单精度）, f64（双精度，默认）
注意： isize 和 usize 的大小取决于目标平台的指针大小（32 位平台为 4 字节，64 位平台为 8 字节）

字符串切片：&str：let s = "Hello, world!";实际上 let s: &str = "Hello, world!";

布尔类型：true 和 false

字符类型：char 表示单个 Unicode 字符（存储为 4 字节），如 'A', '中', '😻'

单元类型：()，其唯一可能的值也是 ()

序列(Range)：for i in 1..=5 {
    println!("{}",i);
}
```



## 4.语句 && 表达式

```rust
let y = y + 5; // 语句
x + y // 表达式；不带分号即表达式，表达式会返回一个值，这样就可以复制给变量

let y = {
        let x = 3;
        x + 1		//不带分号，表达式
    };
```



## 5.函数

```rust
fn add(i: i32, j: i32) -> i32 {
   i + j
 }

```

![img](https://pic2.zhimg.com/80/v2-54b3a6d435d2482243edc4be9ab98153_1440w.png)

**无返回值**

- 函数没有返回值，那么返回一个 `()`
- 通过 `;` 结尾的语句返回一个 `()`

```rust
fn report<T: Debug>(item: T) { //隐式返回一个()
  println!("{:?}", item);
}

fn clear(text: &mut String) -> () {//显式返回空
  *text = String::from("");
}
```



**永不返回的函数**

当用 `!` 作函数返回类型的时候，表示该函数永不返回( diverging functions )，特别的，这种语法往往用做会导致程序崩溃的函数：

```rust
fn dead_end() -> ! {
  panic!("崩溃！");
}
```



## 6.数据转移与拷贝

基础类型，直接拷贝，不涉及到数据的转移。原因在于基础类型都在栈上，也叫**浅拷贝**

```rust
let x = 5;
let y = x;//自动拷贝，不是转移
```

`String` 类型是一个复杂类型，复制则转移

```rust
let s1 = String::from("hello");
let s2 = s1;		//相当于std::move
```



**深拷贝**

必须通过clone函数来深拷贝数据

```rust
let s1 = String::from("hello");
let s2 = s1.clone();
```



**可变引用**

```rust
let mut s = String::from("hello");
{
	let r1 = &mut s;
}
let r2 = &mut s; // 同一作用域，特定数据只能有一个可变引用
```



## 7. 复合类型

### 7.1 切片（slice）

```rust
let s = String::from("hello");

let slice = &s[0..2];
let slice = &s[..2];

let slice = &s[4..len];
let slice = &s[4..];
```



### 7.2 String 与 &str的转换

&str ==> String

- `String::from("hello,world")`
- `"hello,world".to_string()`

String ==> &str

```rust
let s = String::from("hello,world!");
```



### 7.3操作字符串

**追加**

```rust
fn main() {
    let mut s = String::from("Hello ");

    s.push_str("rust");
    println!("追加字符串 push_str() -> {}", s);

    s.push('!');
    println!("追加字符 push() -> {}", s);
}
```

**插入**

可以使用 `insert()` 方法插入单个字符 `char`，也可以使用 `insert_str()` 方法插入字符串字面量

```rust
fn main() {
    let mut s = String::from("Hello rust!");
    s.insert(5, ',');
    println!("插入字符 insert() -> {}", s);
    s.insert_str(6, " I like");
    println!("插入字符串 insert_str() -> {}", s);
}
```

**替换（replace）**

```rust
fn main() {
    let string_replace = String::from("I like rust. Learning rust is my favorite!");
    let new_string_replace = string_replace.replace("rust", "RUST");
    dbg!(new_string_replace);
}
```

**删除（delete）**

与字符串删除相关的方法有 4 个，它们分别是 `pop()`，`remove()`，`truncate()`，`clear()`。这四个方法仅适用于 `String` 类型

-  `pop` —— 删除并返回字符串的最后一个字符
- `remove` —— 删除并返回字符串中指定位置的字符
- `truncate` —— 删除字符串中从指定位置开始到结尾的全部字符
- `clear` —— 清空字符串

**连接**

使用 `+` 或者 `+=` 连接字符串

使用 `format!` 连接字符串

```rust
fn main() {
    let s1 = "hello";
    let s2 = String::from("rust");
    let s = format!("{} {}!", s1, s2);
    println!("{}", s);
}
```



### 7.4 元组

元组是由多种类型组合到一起形成的，因此它是复合类型，元组的长度是固定的，元组中元素的顺序也是固定的。

```rust
fn main() {
   let x: (i32, f64, u8) = (500, 6.4, 1);
    let five_hundred = x.0;
    let six_point_four = x.1;
    let one = x.2;
}
```

