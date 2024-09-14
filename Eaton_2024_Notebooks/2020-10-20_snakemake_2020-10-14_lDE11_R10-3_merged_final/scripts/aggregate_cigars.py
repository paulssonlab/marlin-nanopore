import os
import csv


def cigarsfromsam(samfilepath):
    cigars = {}
    with open(samfilepath, "r") as samfile:
        for line in samfile:
            if line[0] == "@":
                pass
            else:
                splitline = line.split("\t")
                cigars[splitline[0]] = tuple((splitline[3], splitline[5]))
    return cigars


sampaths = snakemake.input["aggsams"]
print(sampaths)
sampaths = [
    item
    for item in sampaths
    if ("subsample=" + str(snakemake.wildcards["subsample"])) == (item.split("/")[-2])
]
print(sampaths)

all_sam_files = []
for chunk_folder in sampaths:
    group_files = os.listdir(chunk_folder)
    group_files = [
        chunk_folder + "/" + item
        for item in group_files
        if "group" in item and item.split(".")[-1] == "sam"
    ]
    all_sam_files += group_files

cigar_dicts = []
for filename in all_sam_files:
    cigar_dict = cigarsfromsam(filename)
    cigar_dicts.append(cigar_dict)

cigar_dict = {
    int(key.split("_")[1]): val
    for subdict in cigar_dicts
    for key, val in subdict.items()
}
output_data = [
    {"barcodeid": key, "startpos": val[0], "cigar": val[1]}
    for key, val in cigar_dict.items()
]

keys = ["barcodeid", "startpos", "cigar"]
with open(snakemake.output["cigartsv"], "w") as outfile:
    dict_writer = csv.DictWriter(outfile, keys, delimiter="\t")
    dict_writer.writeheader()
    dict_writer.writerows(output_data)
