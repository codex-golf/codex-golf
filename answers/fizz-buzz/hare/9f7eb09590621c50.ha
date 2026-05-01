use fmt;
export fn main() void = {
	for (let i: int = 1; i <= 100; i += 1) {
		if (i % 15 == 0) fmt::println("FizzBuzz")!
		else if (i % 3 == 0) fmt::println("Fizz")!
		else if (i % 5 == 0) fmt::println("Buzz")!
		else fmt::printfln("{}", i)!;
	};
};