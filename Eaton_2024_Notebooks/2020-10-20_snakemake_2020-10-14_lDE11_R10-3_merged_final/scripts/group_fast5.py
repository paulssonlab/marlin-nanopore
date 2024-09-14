import os
import shutil

fast5path = snakemake.input["fast5path"]
fast5chunkpath = snakemake.output["fast5chunkpath"]
fast5_chunksize = snakemake.params["fast5_chunksize"]

if os.path.exists(fast5chunkpath):
    shutil.rmtree(fast5chunkpath)
os.makedirs(fast5chunkpath)

fast5_file_list = list(
    sorted([item for item in os.listdir(fast5path) if item[-5:] == "fast5"])
)

for file_idx, item in enumerate(fast5_file_list):
    chunk_id = file_idx // fast5_chunksize
    fast5_chunkid_path = fast5chunkpath + "/chunk_" + str(chunk_id)
    if not os.path.exists(fast5_chunkid_path):
        os.makedirs(fast5_chunkid_path)
    shutil.copyfile(fast5path + "/" + item, fast5_chunkid_path + "/" + item)
