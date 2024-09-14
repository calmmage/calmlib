# 1. import
# 2. init
# 3. dump
# 4. load

from .pb2_example import TUid

if __name__ == "__main__":
    uid = TUid(Uid="uid1", AssociatedItems=["type1", "type2"])

    # str_dump = uid.
