def trim(s, l=None, r=None):
    if l and s.startswith(l):
        s = s[len(l) :]
    if r and s.endswith(r):
        s = s[: -len(r)]
    return s


def rtrim(s, r):
    return trim(s, r=r)


def is_subsequence(sub, main):
    sub_index = 0
    main_index = 0
    while sub_index < len(sub) and main_index < len(main):
        if sub[sub_index] == main[main_index]:
            sub_index += 1
        main_index += 1
    return sub_index == len(sub)
