import csv

import pandas as pd

from Bio import SeqIO

consfile_path = snakemake.input["consfile"]
reffile_path = snakemake.input["reffile"]
cigarfile_path = snakemake.input["cigarfile"]
codebook_path = snakemake.input["inv_barcode_codebook"]

barcode_codebook = {}
codebook_data = pd.read_csv(codebook_path, delimiter="\t")
for _, row in codebook_data.iterrows():
    barcode_codebook[int(row["barcodeid"])] = row["barcode"]

cigar_dict = {}
cigar_data = pd.read_csv(cigarfile_path, delimiter="\t")
for _, row in cigar_data.iterrows():
    cigar_dict[int(row["barcodeid"])] = row["cigar"]

consdict = {
    int(record.id.split(" ")[0].split("_")[1]): str(record.seq)
    for record in SeqIO.parse(consfile_path, "fasta")
}
refdict = {
    int(record.id.split("_")[1]): str(record.seq)
    for record in SeqIO.parse(reffile_path, "fasta")
}

output_data = [
    {
        "barcodeid": key,
        "barcode": val,
        "consensus": consdict[key],
        "reference": refdict[key],
        "cigar": cigar_dict[key],
    }
    for key, val in barcode_codebook.items()
]

keys = ["barcodeid", "barcode", "consensus", "reference", "cigar"]
with open(snakemake.output["outputfile"], "w") as outfile:
    dict_writer = csv.DictWriter(outfile, keys, delimiter="\t")
    dict_writer.writeheader()
    dict_writer.writerows(output_data)
