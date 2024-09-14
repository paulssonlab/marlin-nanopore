import csv
import numpy as np
import pickle as pkl

from matplotlib import pyplot as plt


def get_barcode_codebook(barcode_dict, final_barcode_idx):
    barcode_codebook = {}
    inv_barcode_codebook = {i: [] for i in range(len(final_barcode_idx))}
    for key, val in barcode_dict.items():
        if val in final_barcode_idx.keys():
            barcode_codebook[key] = final_barcode_idx[val]
            inv_barcode_codebook[final_barcode_idx[val]].append(key)
        else:
            barcode_codebook[key] = None
    return barcode_codebook, inv_barcode_codebook


### Get Barcode Histogram ###
inpathlist = snakemake.input["tsv"]

barcode_dict = {}
for filepath in inpathlist:
    with open(filepath, "r") as infile:
        next(infile)
        for line in infile:
            data = line.split("\t")
            barcode_dict[data[0]] = data[1]

barcode_arr = np.array(list(barcode_dict.values()))
unique, counts = np.unique(barcode_arr, return_counts=True)
barcode_counts_dict = {unique[i]: counts[i] for i in range(len(unique))}

with open(snakemake.output["barcode_counts_dict"], "wb") as f:
    pkl.dump(barcode_counts_dict, f, pkl.HIGHEST_PROTOCOL)

vmin, vmax = (0, int(np.percentile(counts, 99.9)))
nbins = min(200, vmax - vmin)

plt.hist(counts, range=(vmin, vmax), bins=nbins)
plt.yscale("log")
plt.axvline(snakemake.params["threshold"], color="salmon")
plt.savefig(snakemake.output["barcode_hist"], dpi=150)

### Threshold Barcodes and Create Index ###

final_barcode_arr = unique[counts >= snakemake.params["threshold"]]
final_barcode_idx = dict(zip(final_barcode_arr, range(len(final_barcode_arr))))
rev_final_barcode_idx = {val: key for key, val in final_barcode_idx.items()}
_, inv_barcode_codebook = get_barcode_codebook(barcode_dict, final_barcode_idx)
# inv_barcode_codebook = {str(key):str(",".join(val)) for key,val in inv_barcode_codebook.items()}
inv_barcode_codebook = [
    {"barcodeid": key, "readlist": val, "barcode": rev_final_barcode_idx[key]}
    for key, val in inv_barcode_codebook.items()
]

keys = ["barcodeid", "readlist", "barcode"]
with open(snakemake.output["inv_barcode_codebook"], "w") as outfile:
    dict_writer = csv.DictWriter(outfile, keys, delimiter="\t")
    dict_writer.writeheader()
    dict_writer.writerows(inv_barcode_codebook)
