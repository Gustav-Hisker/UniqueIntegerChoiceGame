# read n, k, w and j
n, k, w, j = map(int, input().split())

# repeating for the whole game
while True:
    # outputting the highest allowed number
    print(k)
    # reading the input but ignoring it
    submitted_numbers = list(map(int, input().split()))