def test1():
    for i in range(10):
        yield i
if __name__ == "__main__":

    for m in test1():
        print(m)
