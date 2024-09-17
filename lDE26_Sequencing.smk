import os
import shutil

configfile: "./configs/lDE26_Sequencing_config.yaml"

GFA_REF_PATH = config["ref_gfa_path"]
SCRATCH_PATH = config["scratch_path"]
SCRATCH_GFA_REF_PATH = SCRATCH_PATH+"ref.gfa"
FAST5_PATH = config["fast5_path"]

FLOWCELL = config["flowcell"]
KIT = config["kit"]

MIN_READLENGTH = config["min_readlength"]
MAX_READLENGTH = config["max_readlength"]

FAST5_CHUNKSIZE = config["fast5_chunksize"]
READ_SETSIZE = config["read_setsize"]
CHUNK_SIZE = config["chunk_size"]
DEPTH_THRESHOLD = config["depth_threshold"]
N_SUBSAMPLES = config["n_subsamples"]

if not os.path.exists("./logs"):
    os.makedirs("./logs")
    os.makedirs("./logs/cluster")

if not os.path.exists(SCRATCH_GFA_REF_PATH):
    shutil.copyfile(GFA_REF_PATH, SCRATCH_GFA_REF_PATH)
    
## First split all .fast5 files into chunks and guppy basecall

checkpoint groupfast5:
    input:
        fast5path=FAST5_PATH
    output:
        fast5chunkpath=directory(SCRATCH_PATH + "fast5_chunks")
    params:
        fast5_chunksize=FAST5_CHUNKSIZE,
    resources: partition="short", time=180, mem=8000, cpus=1, ntasks=1, optflags=""
    script:
        "scripts/group_fast5.py"

rule guppybasecall:
    input:
        fast5path=SCRATCH_PATH + "fast5_chunks/{chunk}"
    output:
        fastqpath=directory(SCRATCH_PATH + "fastq_chunks/{chunk}")
    params:
        flowcell=FLOWCELL,
        kit=KIT
    resources: partition="gpu_quad", time=600, mem=1600, cpus=1, ntasks=1, optflags="--gres='gpu:1'" #note that this gpu must use the Pascal or newer architecture
    shell:
        "module load gcc/6.2.0; module load cuda/11.2; guppy_basecaller --input_path {input.fast5path} --save_path {output.fastqpath} --flowcell {params.flowcell} --kit {params.kit} --device cuda:0"

def aggregate_fastqpath(wildcards):
    fast5chunkpath_output = checkpoints.groupfast5.get(**wildcards).output["fast5chunkpath"]
    collected_groups = glob_wildcards(os.path.join(fast5chunkpath_output, "{fast5chunkpath}")).fast5chunkpath
    collected_chunks = sorted(list(set([item.split("/")[0] for item in collected_groups if "chunk" in item])))
    expanded_files = directory(expand(SCRATCH_PATH+"fastq_chunks/{fast5group}",fast5group=collected_chunks))
    return expanded_files

checkpoint makereadfiles:
    input:
        aggfastqpaths = aggregate_fastqpath
    output:
        readsetpath = directory(SCRATCH_PATH+"reads")
    params:
        numreads=READ_SETSIZE,
        min_readlength=MIN_READLENGTH,
        max_readlength=MAX_READLENGTH
    resources: partition="short", time=60, mem=8000, cpus=1, ntasks=1, optflags=""
    script:
        "scripts/regroup_reads.py"

rule graphalign:
    input:
        gfa=SCRATCH_PATH+"ref.gfa",
        fastq=SCRATCH_PATH+"reads/{readfile}.fastq"
    output:
        SCRATCH_PATH+"graph_output/{readfile}.gaf"
    resources: partition="short", time=10, mem=500, cpus=1, ntasks=1, optflags=""
    shell:
        "GraphAligner -g {input.gfa} -f {input.fastq} -a {output} -x dbg -b 20 -C 1000"

rule getbarcodes:
    input:
        SCRATCH_PATH+"graph_output/{readfile}.gaf"
    output:
        SCRATCH_PATH+"graph_output/{readfile}.tsv"
    resources: partition="short", time=10, mem=1000, cpus=1, ntasks=1, optflags=""
    script:
        "scripts/get_barcodes.py"

def aggregate_tsvs(wildcards):
    readsetpath_output = checkpoints.makereadfiles.get(**wildcards).output["readsetpath"]
    collected_groups = glob_wildcards(os.path.join(readsetpath_output, "{readsetpath}")).readsetpath
    collected_groups = [SCRATCH_PATH+"graph_output/" + group.split("/")[0][:-6] + ".tsv" for group in collected_groups if group.split("/")[0][-5:] == "fastq"]
    return collected_groups

def aggregate_fastqs(wildcards):
    readsetpath_output = checkpoints.makereadfiles.get(**wildcards).output["readsetpath"]
    collected_groups = glob_wildcards(os.path.join(readsetpath_output, "{readsetpath}")).readsetpath
    collected_groups = [SCRATCH_PATH+"reads/" + group for group in collected_groups if group.split("/")[0][-5:] == "fastq"]
    return collected_groups

rule setthreshold:
    input:
        tsv = aggregate_tsvs
    output:
        barcode_hist = SCRATCH_PATH+"graph_output/barcode_counts.png",
        barcode_counts_dict = SCRATCH_PATH+"graph_output/barcode_counts_dict.pkl",
        inv_barcode_codebook = SCRATCH_PATH+"graph_output/inv_codebook.tsv"
    params:
        threshold=DEPTH_THRESHOLD
    resources: partition="short", time=30, mem=16000, cpus=1, ntasks=1, optflags=""
    script:
        "scripts/set_barcode_threshold.py"

# the checkpoint that shall trigger re-evaluation of the DAG
checkpoint groupbarcodes:
    input:
        inv_barcode_codebook = SCRATCH_PATH+"graph_output/inv_codebook.tsv",
        tsv=aggregate_tsvs,
        fastq=aggregate_fastqs,
        gfa=SCRATCH_PATH+"ref.gfa"
    output:
        readgroups = directory(SCRATCH_PATH+"readgroups"),
        grouprefs = directory(SCRATCH_PATH+"grouprefs")
    params:
        chunksize=CHUNK_SIZE,
        subsample_list=N_SUBSAMPLES
    resources: partition="short", time=120, mem=32000, cpus=1, ntasks=1, optflags=""
    script:
        "scripts/group_barcodes.py"

rule madakaconsensus:
    input:
        readgroup = SCRATCH_PATH+"readgroups/subsample={subsample}/{chunk}",
        groupref = SCRATCH_PATH+"grouprefs/subsample={subsample}/{chunk}"
    output:
        consensus = directory(SCRATCH_PATH+"consensus/subsample={subsample}/{chunk}"),
        alignment = directory(SCRATCH_PATH+"alignment/subsample={subsample}/{chunk}"),
        completion_file = SCRATCH_PATH+"consensus/subsample={subsample}/{chunk}/completed.txt"
    resources: partition="short", time=180, mem=500, cpus=1, ntasks=1, optflags=""
    run:
        groups = os.listdir(list({input.readgroup})[0])
        groups = [item.split(".")[0] for item in groups if "group" in item]

        shell_str = "mkdir {output.alignment}"
        shell(shell_str)

        for group in groups:
            shell_str = "medaka_consensus -i {input.readgroup}/" + str(group) + ".fastq -d {input.groupref}/" + str(group) + ".fasta -o {output.consensus}/" + str(group) +\
            "; minimap2 -ax map-ont {input.groupref}/" + str(group) + ".fasta {output.consensus}/" + str(group) + "/consensus.fasta > {output.alignment}/" + str(group) + ".sam"
            shell(shell_str)
        with open(output.completion_file,"w") as output_file:
            output_file.write("Done.")

def aggregate_consensus_completion_files(wildcards):
    readgroups_output = checkpoints.groupbarcodes.get(**wildcards).output["readgroups"]
    collected_groups = glob_wildcards(os.path.join(readgroups_output, "{readgroup}.fastq")).readgroup
    collected_chunks = sorted(list(set(["/".join(item.split("/")[0:2]) for item in collected_groups]))) ##'subsample=50/chunk_0'
    expanded_completion_files = expand(SCRATCH_PATH+"consensus/{readgroup}/completed.txt",readgroup=collected_chunks)
    return expanded_completion_files

def aggregate_consensus(wildcards):
    readgroups_output = checkpoints.groupbarcodes.get(**wildcards).output["readgroups"]
    collected_groups = glob_wildcards(os.path.join(readgroups_output, "{readgroup}.fastq")).readgroup
    collected_chunks = sorted(list(set(["/".join(item.split("/")[0:2]) for item in collected_groups]))) ##'subsample=50/chunk_0'
    expanded_files = directory(expand(SCRATCH_PATH+"consensus/{readgroup}",readgroup=collected_chunks))
    expanded_completion_files = expand(SCRATCH_PATH+"consensus/{readgroup}/completed.txt",readgroup=collected_chunks)
    return expand(SCRATCH_PATH+"consensus/{readgroup}",readgroup=collected_chunks)

def aggregate_grouprefs(wildcards):
    readgroups_output = checkpoints.groupbarcodes.get(**wildcards).output["readgroups"]
    collected_groups = glob_wildcards(os.path.join(readgroups_output, "{readgroup}.fastq")).readgroup
    collected_chunks = sorted(list(set(["/".join(item.split("/")[0:2]) for item in collected_groups]))) ##'subsample=50/chunk_0'
    expanded_files = directory(expand(SCRATCH_PATH+"grouprefs/{readgroup}",readgroup=collected_chunks))
    return expand(SCRATCH_PATH+"grouprefs/{readgroup}",readgroup=collected_chunks)

def aggregate_sams(wildcards):
    readgroups_output = checkpoints.groupbarcodes.get(**wildcards).output["readgroups"]
    collected_groups = glob_wildcards(os.path.join(readgroups_output, "{readgroup}.fastq")).readgroup
    collected_chunks = sorted(list(set(["/".join(item.split("/")[0:2]) for item in collected_groups]))) ##'subsample=50/chunk_0'
    return expand(SCRATCH_PATH+"alignment/{readgroup}",readgroup=collected_chunks)

rule check_consensus:
    input:
        aggcons_comp = aggregate_consensus_completion_files
    output:
        checked_cons_file = SCRATCH_PATH+"consensus_subsample={subsample}_completed.txt"
    resources: partition="short", time=120, mem=16000, cpus=1, ntasks=1, optflags=""
    run:
        with open(output.checked_cons_file,"w") as output_file:
            output_file.write("Done.")

rule aggconsensus:
    input:
        aggcons = aggregate_consensus,
        checked_cons_file = SCRATCH_PATH+"consensus_subsample={subsample}_completed.txt"
    output:
        consfile = SCRATCH_PATH+"consensus_subsample={subsample}.fasta"
    resources: partition="short", time=120, mem=16000, cpus=1, ntasks=1, optflags=""
    run:
        all_consensus_files = []
        chunk_folders = [item for item in list({input.aggcons})[0] if ("subsample=" + str(wildcards.subsample))==(item.split("/")[-2])]
        for chunk_folder in chunk_folders:
            group_folders = os.listdir(chunk_folder)
            group_files = [chunk_folder + "/" + item + "/consensus.fasta" for item in group_folders if "group" in item]
            all_consensus_files += group_files

        outstr = ""
        for filename in all_consensus_files:
            with open(filename,"r") as infile:
                outstr += infile.read()

        with open(list({output.consfile})[0],"w") as outfile:
            outfile.write(outstr)

rule agggrouprefs:
    input:
        aggregate_grouprefs
    output:
        reffile = SCRATCH_PATH+"references_subsample={subsample}.fasta"
    resources: partition="short", time=120, mem=16000, cpus=1, ntasks=1, optflags=""
    run:
        print(input)
        all_ref_files = []
        chunk_folders = [item for item in list({input})[0] if ("subsample=" + str(wildcards.subsample))==(item.split("/")[-2])]
        for chunk_folder in chunk_folders:
            group_files = os.listdir(chunk_folder)
            group_files = [chunk_folder + "/" + item for item in group_files if "group" in item and item.split(".")[-1] == "fasta"]
            all_ref_files += group_files

        outstr = ""
        for filename in all_ref_files:
            with open(filename,"r") as infile:
                outstr += infile.read()

        with open(list({output.reffile})[0],"w") as outfile:
            outfile.write(outstr)

rule aggregatecigars:
    input:
        aggsams = aggregate_sams
    output:
        cigartsv = SCRATCH_PATH+"cigars_subsample={subsample}.tsv"
    resources: partition="short", time=120, mem=16000, cpus=1, ntasks=1, optflags=""
    script:
        "scripts/aggregate_cigars.py"

rule outputtsv:
    input:
        consfile = SCRATCH_PATH+"consensus_subsample={subsample}.fasta",
        reffile = SCRATCH_PATH+"references_subsample={subsample}.fasta",
        cigarfile = SCRATCH_PATH+"cigars_subsample={subsample}.tsv",
        inv_barcode_codebook = SCRATCH_PATH+"graph_output/inv_codebook.tsv"
    output:
        outputfile = SCRATCH_PATH+"output_subsample={subsample}.tsv"
    resources: partition="short", time=120, mem=16000, cpus=1, ntasks=1, optflags=""
    script:
        "scripts/gather_data.py"

rule aggregate_outputs:
    input:
        tsv_output = expand(SCRATCH_PATH+"output_subsample={subsample}.tsv",subsample=N_SUBSAMPLES)
    output:
        final_output = SCRATCH_PATH+"output.tsv"
    resources: partition="short", time=120, mem=16000, cpus=1, ntasks=1, optflags=""
    script:
        "scripts/merge_outputs.py"
