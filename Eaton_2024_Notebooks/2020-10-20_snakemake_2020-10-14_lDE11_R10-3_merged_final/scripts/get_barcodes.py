import csv
import numpy as np

cigar_dict = {}
with open(snakemake.input[0], "r") as infile:
    for line in infile:
        data = line.split("\t")
        read_id = data[0].split(" ")[0]
        if ">" in data[5]:
            cigar_dict[read_id] = (
                "+",
                int(data[7]),
                int(data[8]),
                data[5],
                data[15].split(":")[-1][:-1],
            )
        else:
            cigar_dict[read_id] = (
                "-",
                int(data[7]),
                int(data[8]),
                data[5],
                data[15].split(":")[-1][:-1],
            )

barcode_dict = {}
for key in cigar_dict.keys():
    cigar = cigar_dict[key]
    if "GFP" in cigar[3] and "SPACER4" in cigar[3]:
        if cigar[0] == "-":
            barcode = cigar[3].split("<")
            barcode = barcode[::-1]
        elif cigar[0] == "+":
            barcode = cigar[3].split(">")
        barcode = barcode[:-1]
        barcode = (
            np.array(["ON" in item for item in barcode if "BIT" in item])
            .astype(int)
            .astype(str)
            .tolist()
        )
        barcode = "".join(barcode)
        barcode_dict[key] = barcode

barcode_dict = [
    {"readname": key, "barcode": val, "cigar": cigar_dict[key]}
    for key, val in barcode_dict.items()
]

keys = ["readname", "barcode", "cigar"]
with open(snakemake.output[0], "w") as outfile:
    dict_writer = csv.DictWriter(outfile, keys, delimiter="\t")
    dict_writer.writeheader()
    dict_writer.writerows(barcode_dict)
