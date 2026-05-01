for n in range(1,201):
 if sum(i*(n%i<1)for i in range(1,n))>n:print(n)
