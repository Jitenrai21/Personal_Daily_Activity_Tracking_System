# from collections import Counter
# res = Counter()
# res['check'] += 1
# print(res)

# check = {}
# check['test'] += 1
# print(check)

# values = [5,1,3,2]
# values.sort()
# print(values)

# from collections import Counter
# def steadyGene(gene):
#     # Write your code here
#     val_counts = Counter(gene)
#     gene = list(gene)
#     genes = ['A', 'C', 'T', 'G']
#     # gene_map = {'A':0, 'C':0, 'T':0, 'G':0}

#     gene_values = []
#     for gene_value in val_counts.elements():
#         gene_values.append(gene_value)
#     for gene_val in genes:
#         if gene_val not in gene_values:
#             val_counts[gene_val] = 0
#     print(val_counts)
#     values = []
#     for value in val_counts.values():
#         values.append(value)
#     values.sort(reverse=True)
#     print(values)
# steadyGene("GAAATAAA")

# def pairs(k, arr):
#     # Write your code here
#     # counts = 0
#     # arr.sort()
#     # for i in range(len(arr)):
#     #     for j in range(i+1, len(arr)):
#     #         diff = arr[j] - arr[i]
#     #         if diff == k:
#     #             counts += 1
#     # return counts
#     counts = 0
#     arr.sort()
#     for i in range(len(arr)):
#         anchor = arr[i]
#         search = anchor + k
#         if search in arr:
#             counts += 1

rows = [[]] * 5
print(rows)
