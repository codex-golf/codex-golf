main=mapM_(putStrLn.f)[1..100]
f n|mod n 15<1="FizzBuzz"|mod n 3<1="Fizz"|mod n 5<1="Buzz"|1>0=show n