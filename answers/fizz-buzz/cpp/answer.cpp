#include<cstdio>
char b[9];int main(){for(int i=1;i<101;i++){sprintf(b,"%d",i);puts(i%15<1?"FizzBuzz":i%3<1?"Fizz":i%5<1?"Buzz":b);}}