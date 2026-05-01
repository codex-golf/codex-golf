def h(n):
 while n>4:n=sum(int(d)**2 for d in str(n))
 return n==1
print(*filter(h,range(1,194)),sep='\n')
