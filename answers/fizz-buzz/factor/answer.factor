USING: combinators io kernel math math.parser sequences ;
1 100 [a..b] [
  {
    { [ dup 15 mod 0 = ] [ drop "FizzBuzz" ] }
    { [ dup 3 mod 0 = ] [ drop "Fizz" ] }
    { [ dup 5 mod 0 = ] [ drop "Buzz" ] }
    [ number>string ]
  } cond print
] each