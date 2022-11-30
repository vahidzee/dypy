# Dynamic Code (DyCode): a toolset for dynamic python code manipulations

Have you ever found yourself coding up boilerplates to handle different scenarios? It's most likely that you have thought about using python's `eval` or `exec` in order to decouple some part of your code to be specified and evaluated later on at run-time. But, you have probably also come accross people who discourage you from using `eval`/`exec`. This is because programs with `eval`/`exec` are considered vulnarable and can be used to execute malicious code.

While this is true in general, but in many cases, you do not care about security concerns, and your highest priority is implementing a quick solution to a general problem which could be solved by using `eval` or `exec`. This is where DyCode comes in. It allows you to use `eval` and `exec` effectively by providing utilities to dynamically compile code, lookup variables and lazily evaluate them.

**Table of Contents**
- [Dynamic Code (DyCode): a toolset for dynamic python code manipulations](#dynamic-code-dycode-a-toolset-for-dynamic-python-code-manipulations)
  - [Installation](#installation)
  - [Usage](#usage)
    - [Dynamic Evaluation](#dynamic-evaluation)
      - [Variable Lookup](#variable-lookup)
      - [Dynamic Function Evaluation](#dynamic-function-evaluation)
    - [Variable Assignment](#variable-assignment)
  - [License](#license)
  - [Citation](#citation)

## Installation

```bash
pip install dycode
```

## Usage

### Dynamic Evaluation

You can use `dycode.eval` to combine the functionality of `dycode.eval_function` (see [here](#dynamic-function-evaluation)) and `dycode.get_value` (see [here](#variable-lookup)). You can do as follows:

```python
import dycode

dycode.eval("math.cos") # <function <lambda> at MEM_ADDRESS> (math is imported through get_value)
dycode.eval("math.cos", dynamic_args=True)(2, verbose=True) # 3, verbose is ignored (and math is imported through get_value)
dycode.eval("def my_function(x): return x + 1", function_of_interest="my_function") # <function my_function at MEM_ADDRESS>
dycode.eval("def my_function(x): return x + y", function_of_interest="my_function", context={"y": 2})(2) # 4
```


#### Variable Lookup

You can use `dycode.get_value` to lookup a variable as a string and then evaluate it. This is useful when you want to use a variable that is not defined in the current scope. You can do as follows:

```python
from dycode import get_value

get_value("math.pi") # 3.141592653589793
get_value("math.cos(0)") # won't evaluate, this is not a variable but a call to a variable
get_value("math.cos")(0) # 1.0

import math
get_value("cos", context=math) # math.cos

get_value("something_that_does_not_exist") # raises NameError
get_value("something_that_does_not_exist", strict=False) # None
```

`get_value` supports looking up variables in a module or package in your current working directory as well (as opposed to python's `import` which only supports looking up variables in the python standard library and installed packages). This is useful when you want to create a script that can be run from anywhere and still be able to access variables in the current working directory. 

For example, imagine you create your own python package with a runnable script that sorts files in a directory. You can use `get_value` to lookup a `config.sort` function in the current working directory. This way, you can create a `config.py` file in the current working directory and define your own sorting function. Or use a default sorting function if the `config.py` file does not exist. 

Your code would look like this:

```python
from dycode import get_value

def sort_files():
    sort_function = get_value("config.sort", strict=False) or default_sort
    # do something with sort
```

Although this example is somewhat contrived, such a use case is very common in data science and machine learning. Imagine writing a package for training a Deep Learning model. You can use `get_value` to lookup custom Dataset classes and model implementations and this way, people can use your package without the need to modifying your code, because they can simply inject their own implementations in places where you have used `get_value`.

Another potential use case is defining Neural Network layers. You can use `get_value` to lookup custom layers and use them in your model. Such as:

```python
from dycode import get_value
import torch

class MyLinearBlock(torch.nn.Module):
    def __init__(self, in_features, out_features, activation="torch.nn.ReLU"):
        super().__init__()
        self.linear = torch.nn.Linear(in_features, out_features)
        self.activation = get_value(activation, strict=False) 

    def forward(self, x):
        x = self.linear(x)
        x = self.activation(x) if self.activation else x
        return x
```

This way, you can change the activation function by simply changing the `activation` argument. For example, you can use `torch.nn.Sigmoid` or `torch.nn.Tanh` or even a custom activation function that you have defined in the current working directory or use one from a 3rd party package.

#### Dynamic Function Evaluation

What if you want to generate python programs dynamically? Meaning that you have a string that contains python code and you want to inject it into your program.  You can use `dycode.eval_function` to evaluate a piece of code and retrieve a function. You can do as follows:

```python
from dycode import eval_function

eval_function("lambda x: x + 1") # <function <lambda> at MEM_ADDRESS>

eval_function("def my_function(x): return x + 1") # wont work, this is not a function, 
# but a code block and you need to mention your function_of_interest in that code block

eval_function("def my_function(x): return x + 1", function_of_interest="my_function") # <function my_function at MEM_ADDRESS>
```

`eval_function` accepts three types of function descriptors:

1. A lambda function, e.g. `lambda x: x + 1`, or a code which evaluates to a callable object, `math.cos` (in this case, the values being looked up should be present in the evaluation context, more on this later).
2. A code block, which can contain multiple lines and functions, in which case you need to specify the name of the function of interest using the `function_of_interest` argument. `eval_function` will evaluate the code block and retrieve your function of interest.
3. A dictionary of "code", ["context", "function_of_interest"] pairs. Useful when you are using `eval_function` on top of a configuration file, in which case you can specify the code and the context for each function of interest.

When evaluating a function descriptor, you can specify a context in which the code will be evaluated. This is useful when you want to use variables that are not defined in the current scope. `dycode` has a context registry that you can use as a global context for all your function evaluations.

```python
from dycode import eval_function, register_context
import math

register_context(math, "math") # register math package as a context
# you can also use register(math), which will use the name of the package as the context name

eval_function("math.cos") # <function <lambda> at MEM_ADDRESS> (math is looked up through the context registry)
```

You can also specify a context for each function evaluation using the `context` argument. The context is a dictionary of variable names and their values. You can do as follows:

```python
eval_function("def my_function(x): return x + y", function_of_interest="my_function", context={"y": 1})(2) # 3
```

You can also optionally set `dynamic_args=True`, when evaluating a function. This will create a function that intelligently evaluates its arguments, by wrapping it using `dycode.dynamic_args_wrapper`. Functions wrapped by `dycode.dynamic_args_wrapper` preprocess arguments passed to them, and ignore arguments that are not defined in the function signature. For instance:

```python
eval_function("lambda x: x + 1", dynamic_args=True)(2, verbose=True) # 3, verbose is ignored
```

### Variable Assignment

There are times when you want to assign a variable in a dynamic manner. Meaning that you want to change a variable's value that is not necessarily defined in the current scope. You can use `dycode.set_value` to do so.  You can do as follows:

```python
from dycode import set_value

set_value("some_package.my_function", lambda x: x + 1)

# changing the value of pi in math package
set_value("math.pi", 3.14) 

# now if you import math, math.pi will be 3.14
import math
math.pi # 3.14
```

## License

DyCode is licensed under the MIT License. See [LICENSE](LICENSE) for the full license text.

## Citation

If you use DyCode in your research, please cite this repository as described in [CITATION.cff](CITATION.cff).
