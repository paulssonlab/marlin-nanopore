import os
from Bio import SeqIO

read_idx = 0
readfile_idx = 0
output_records = []

fastqpath_list = snakemake.input["aggfastqpaths"]
min_readlength = snakemake.params["min_readlength"]
max_readlength = snakemake.params["max_readlength"]
numreads = snakemake.params["numreads"]
readfile_dir = snakemake.output["readsetpath"]

if os.path.exists(readfile_dir):
    shutil.rmtree(readfile_dir)
os.makedirs(readfile_dir)

output_records = []
for fastq_dir in fastqpath_list:
    passed_read_path = fastq_dir + "/pass"
    for filename in os.listdir(passed_read_path):
        if ".fastq" in filename:
            with open(passed_read_path + "/" + filename, "r") as infile:
                record = []
                for i, line in enumerate(infile):
                    record.append(line)
                    if i % 4 == 1:
                        record_len = len(line[:-1])
                    if i % 4 == 3:
                        if (record_len <= max_readlength) and (
                            record_len >= min_readlength
                        ):
                            output_records += record
                            record = []
                            read_idx += 1
                        else:
                            record = []
                        if read_idx >= numreads:
                            with open(
                                readfile_dir
                                + "/readset_"
                                + str(readfile_idx)
                                + ".fastq",
                                "w",
                            ) as output_handle:
                                output_handle.writelines(output_records)
                            read_idx = 0
                            readfile_idx += 1
                            output_records = []

#         if ".fastq" in filename:
#             input_records = list(
#                 SeqIO.parse(passed_read_path + "/" + filename, "fastq")
#             )
#             for record in input_records:
#                 record_len = len(record.seq)
#                 if (record_len <= max_readlength) and (record_len >= min_readlength):

#                     output_records.append(record)
#                     read_idx += 1
#                     if read_idx >= numreads:
#                         with open(
#                             readfile_dir + "/readset_" + str(readfile_idx) + ".fastq",
#                             "w",
#                         ) as output_handle:
#                             SeqIO.write(output_records, output_handle, "fastq")

#                         read_idx = 0
#                         readfile_idx += 1
#                         output_records = []

if read_idx > 0:
    with open(
        readfile_dir + "/readset_" + str(readfile_idx) + ".fastq", "w"
    ) as output_handle:
        output_handle.writelines(output_records)
    # with open(
    #     readfile_dir + "/readset_" + str(readfile_idx) + ".fastq", "w"
    # ) as output_handle:
    #     SeqIO.write(output_records, output_handle, "fastq")
