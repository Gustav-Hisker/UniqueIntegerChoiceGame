# import random to get randomness
from random import randint

# read n, k, w and j
n, k, w, j = map(int, input().split())

# repeating for the whole game
while True:
    # outputting random integer
    print(randint(1, n))
    # reading the input but ignoring it
    submitted_numbers = list(map(int, input().split()))