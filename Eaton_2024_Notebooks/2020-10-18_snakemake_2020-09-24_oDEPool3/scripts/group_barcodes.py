import csv
import ast
import os
import shutil
import numpy as np
import pandas as pd

from Bio import SeqIO

from matplotlib import pyplot as plt


def make_seg_dict(gfafile):
    segment_dict = {}
    with open(gfafile, "r") as infile:
        for line in infile:
            if line[0] == "S":
                splitline = line.split("\t")
                segment_dict[splitline[1]] = splitline[2][:-1]
    return segment_dict


def generate_reference(cigar, segment_dict):
    if cigar[0] == "+":
        traversal = cigar[3].split(">")[1:]
        ref = "".join(list(map(lambda seg: segment_dict[seg], traversal)))
    elif cigar[0] == "-":
        traversal = cigar[3].split("<")[1:][::-1]
        ref = "".join(list(map(lambda seg: segment_dict[seg], traversal)))
    return ref


### Get Barcode to Read Map ###

inv_codebook_path = snakemake.input["inv_barcode_codebook"]
tsv_paths = snakemake.input["tsv"]
inv_barcode_codebook = {}
codebook_data = pd.read_csv(inv_codebook_path, delimiter="\t")
for _, row in codebook_data.iterrows():
    inv_barcode_codebook[int(row["barcodeid"])] = ast.literal_eval(row["readlist"])

cigar_dict = {}
for filepath in tsv_paths:
    with open(filepath, "r") as csvfile:
        reader = csv.DictReader(csvfile, delimiter="\t")
        for row in reader:
            cigar_dict[row["readname"]] = ast.literal_eval(row["cigar"])

### Make Segment Dictionary ###
gfafile = snakemake.input["gfa"]
seg_dict = make_seg_dict(gfafile)

import psutil

### Make fastq lookup ###
fastqlist = snakemake.input["fastq"]
record_dict = {}
for i, fastqfile in enumerate(fastqlist):
    read_name_list = []
    read_list = []
    with open(fastqfile, "r") as infile:
        for i, line in enumerate(infile):
            if i % 4 == 0:
                read_name_list.append(line.rstrip().split()[0][1:])
            elif i % 4 == 1:
                read_list.append(line.rstrip())
    working_dict = dict(zip(read_name_list, read_list))
    record_dict.update(working_dict)
    del working_dict

readgroup_path = snakemake.output["readgroups"]
if os.path.exists(readgroup_path):
    shutil.rmtree(readgroup_path)
os.makedirs(readgroup_path)

groupref_path = snakemake.output["grouprefs"]
if os.path.exists(groupref_path):
    shutil.rmtree(groupref_path)
os.makedirs(groupref_path)

chunksize = snakemake.params["chunksize"]
subsample_list = snakemake.params["subsample_list"]

for key, val in inv_barcode_codebook.items():

    ref_str = ""
    ref_seq = generate_reference(cigar_dict[val[0]], seg_dict)
    ref_str += ">group_" + str(key) + "\n"
    ref_str += ref_seq + "\n"

    for subsample in subsample_list:
        refchunkpath = (
            groupref_path
            + "/subsample="
            + str(subsample)
            + "/chunk_"
            + str(key // chunksize)
        )
        if not os.path.exists(refchunkpath):
            os.makedirs(refchunkpath)

        with open(refchunkpath + "/group_" + str(key) + ".fasta", "w") as outfile:
            outfile.write(ref_str)

        readchunkpath = (
            readgroup_path
            + "/subsample="
            + str(subsample)
            + "/chunk_"
            + str(key // chunksize)
        )

        if subsample == None:
            subsampled_reads = val
        else:
            subsampled_reads = list(
                np.random.choice(val, size=subsample, replace=False)
            )

        if not os.path.exists(readchunkpath):
            os.makedirs(readchunkpath)

        out_str = ""

        for read_name in subsampled_reads:
            seq_record = record_dict[read_name]
            out_str += "@" + str(read_name) + "\n"
            out_str += seq_record + "\n"

        with open(readchunkpath + "/group_" + str(key) + ".fastq", "w") as outfile:
            outfile.write(out_str)
