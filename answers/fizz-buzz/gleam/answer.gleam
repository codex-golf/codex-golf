import gleam/int
import gleam/io

pub fn main() {
  do(1)
}

fn do(i: Int) {
  case i > 100 {
    True -> Nil
    False -> {
      case i % 15, i % 3, i % 5 {
        0, _, _ -> io.println("FizzBuzz")
        _, 0, _ -> io.println("Fizz")
        _, _, 0 -> io.println("Buzz")
        _, _, _ -> io.println(int.to_string(i))
      }
      do(i + 1)
    }
  }
}