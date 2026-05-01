def p(n):
 c=bin(n).count('1')
 return c>1and all(c%i for i in range(2,c))
print(*filter(p,range(3,51)),sep='\n')
