SYS_WRITE = 1

.data
fizz: .ascii "Fizz"
buzz: .ascii "Buzz"
nl: .byte '\n'

.text
mov $1, %r12

nLoop:
    cmp $101, %r12
    jge done
    
    # Check div by 3 and 5
    mov %r12d, %eax
    mov $15, %ecx
    xor %edx, %edx
    div %ecx
    test %edx, %edx
    jz fizzBuzz
    
    mov %r12d, %eax
    mov $3, %ecx
    xor %edx, %edx
    div %ecx
    test %edx, %edx
    jz justFizz
    
    mov %r12d, %eax
    mov $5, %ecx
    xor %edx, %edx
    div %ecx
    test %edx, %edx
    jz justBuzz
    
    # Print number
    mov %r12d, %eax
    xor %r8d, %r8d
    mov $10, %r9d
digitLoop:
    xor %edx, %edx
    div %r9d
    add $'0', %edx
    push %rdx
    inc %r8d
    test %eax, %eax
    jnz digitLoop
printDigits:
    pop %rax
    mov %al, -1(%rsp)
    mov $SYS_WRITE, %eax
    mov $1, %edi
    lea -1(%rsp), %rsi
    mov $1, %edx
    syscall
    dec %r8d
    jnz printDigits
    jmp printNL

fizzBuzz:
    mov $SYS_WRITE, %eax
    mov $1, %edi
    mov $fizz, %esi
    mov $4, %edx
    syscall
    mov $SYS_WRITE, %eax
    mov $1, %edi
    mov $buzz, %esi
    mov $4, %edx
    syscall
    jmp printNL

justFizz:
    mov $SYS_WRITE, %eax
    mov $1, %edi
    mov $fizz, %esi
    mov $4, %edx
    syscall
    jmp printNL

justBuzz:
    mov $SYS_WRITE, %eax
    mov $1, %edi
    mov $buzz, %esi
    mov $4, %edx
    syscall

printNL:
    mov $SYS_WRITE, %eax
    mov $1, %edi
    mov $nl, %esi
    mov $1, %edx
    syscall
    
    inc %r12
    jmp nLoop

done: