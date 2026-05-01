fn main(){for i in 1..101{print!("{}
",[&i.to_string(),"Fizz","Buzz","FizzBuzz"][(i*i+14)%15*2/9])}}