program f
do i=1,100
if(mod(i,15)==0)then
print'(A)','FizzBuzz'
elseif(mod(i,3)==0)then
print'(A)','Fizz'
elseif(mod(i,5)==0)then
print'(A)','Buzz'
else
print'(i0)',i
endif
enddo
end