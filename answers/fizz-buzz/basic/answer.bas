for i as integer=1 to 100
dim s as string=""
if i mod 3=0 then s="Fizz"
if i mod 5=0 then s+="Buzz"
if s="" then s=str(i)
print s
next