print(*(i for i in range(2,100)if all(i%j for j in range(2,i))),sep='\n')
