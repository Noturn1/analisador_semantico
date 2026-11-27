    $topo = 0
    goto main

fat:
    ifFalse fat.n <= 1 goto L1
    return 1
L1:
    t1 = fat.n - 1
    param t1
    $pilha[$topo] = fat.n
    $topo = $topo + 1
    fat.n = t1
    t2 = call fat, 1
    $topo = $topo - 1
    fat.n = $pilha[$topo]
    t3 = fat.n * t2
    return t3

media:
    t4 = inttofloat(media.a)
    t5 = t4 + media.b
    t6 = t5 / 2.0
    return t6

mostra:
    print mostra.msg
    return

main:
    x = 0
    m = 0.0
    read x
    param x
    param 2.5
    media.a = x
    media.b = 2.5
    t7 = call media, 2
    m = t7
    t8 = floattoint(m)
    param x
    fat.n = x
    t9 = call fat, 1
    t10 = t8 + t9
    k = t10
    t11 = x > 0
    t12 = !t11
    neg = t12
    t13 = -x
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
    t15 = "zero"
    param t15
    mostra.msg = t15
    call mostra, 1
    goto L6
L8:
L9:
    t16 = "pequeno"
    param t16
    mostra.msg = t16
    call mostra, 1
    goto L6
L10:
    t17 = "grande"
    param t17
    mostra.msg = t17
    call mostra, 1
    goto L6
L5:
    if k == 0 goto L7
    if k == 1 goto L8
    if k == 2 goto L9
    goto L10
L6:
    param 2.0
    param -1.0
    $b = 2.0
    $e = -1.0
    t18 = call potencia_float, 2
    p = t18
    print m
    return 0

potencia_float:
    $neg = $e < 0.0
    ifFalse $neg goto potencia_float_1
    $e = -$e
potencia_float_1:
    $r = 1.0
    $s = $b
    $n = floattoint($e)
    $x = inttofloat($n)
    $f = $e - $x
potencia_float_2:
    ifFalse $n > 0 goto potencia_float_4
    $x = $n % 2
    ifFalse $x == 1 goto potencia_float_3
    $r = $r * $b
potencia_float_3:
    $b = $b * $b
    $n = $n / 2
    goto potencia_float_2
potencia_float_4:
    ifFalse $f > 0.0 goto potencia_float_9
    if $s > 0.0 goto potencia_float_5
    $r = 0.0
    if $s == 0.0 goto potencia_float_9
    $r = 0.0 / 0.0
    goto potencia_float_9
potencia_float_5:
    $x = $s
    if $x > 1.0 goto potencia_float_6
    $x = 1.0
potencia_float_6:
    $y = $s / $x
    $y = $x + $y
    $y = $y / 2.0
    ifFalse $y < $x goto potencia_float_7
    $x = $y
    goto potencia_float_6
potencia_float_7:
    $s = $x
    $f = $f * 2.0
    ifFalse $f >= 1.0 goto potencia_float_8
    $r = $r * $s
    $f = $f - 1.0
potencia_float_8:
    if $f > 0.0 goto potencia_float_5
potencia_float_9:
    ifFalse $neg goto potencia_float_10
    $r = 1.0 / $r
potencia_float_10:
    return $r
