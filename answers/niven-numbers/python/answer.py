print(*[n for n in range(1,101)if n%sum(map(int,str(n)))<1],sep='\n')
