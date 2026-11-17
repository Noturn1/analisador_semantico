fat:
    ifFalse n <= 1 goto L1
    return 1
L1:
    t1 = n - 1
    param t1
    t2 = call fat, 1
    t3 = n * t2
    return t3

media:
    t4 = inttofloat(a)
    t5 = t4 + b
    t6 = t5 / 2.0
    return t6

mostra:
    param msg
    call puts, 1
    return

main:
    x = 0
    m = 0.0
    x = call input, 0
    param x
    param 2.5
    t7 = call media, 2
    m = t7
    t8 = floattoint(m)
    param x
    t9 = call fat, 1
    t10 = t8 + t9
    k = t10
    t11 = x > 0
    t12 = ! t11
    neg = t12
    t13 = - x
    y = t13
L2:
    ifFalse true goto L3
    ifFalse x <= 0 goto L4
    goto L3
L4:
    t14 = x - 1
    x = t14
    goto L2
L3:
    goto L5
L7:
    param 'zero'
    call mostra, 1
    goto L6
L8:
L9:
    param 'pequeno'
    call mostra, 1
    goto L6
L10:
    param 'grande'
    call mostra, 1
    goto L6
L5:
    if k == 0 goto L7
    if k == 1 goto L8
    if k == 2 goto L9
    goto L10
L6:
    t15 = 2.0 ^ -1.0
    p = t15
    param m
    call puts, 1
    return 0
