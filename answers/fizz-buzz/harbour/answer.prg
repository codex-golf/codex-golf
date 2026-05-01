local i,s
for i:=1 to 100
s:=iif(i%15==0,"FizzBuzz",iif(i%3==0,"Fizz",iif(i%5==0,"Buzz",hb_ntos(i))))+chr(10)
OutStd(s)
next