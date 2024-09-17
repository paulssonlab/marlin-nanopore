import pandas as pd

output_tsv_list = snakemake.input["tsv_output"]
final_output = snakemake.output["final_output"]

output_df = []
for output_tsv in output_tsv_list:
    subsample_num = output_tsv.split("/")[-1][17:].split(".")[0]
    if subsample_num == 0:
        subsample_num = None
    else:
        subsample_num = int(subsample_num)
    in_data = pd.read_csv(output_tsv, delimiter="\t")
    in_data["subsample"] = subsample_num
    output_df.append(in_data)

output_df = pd.concat(output_df)
output_df.to_csv(final_output, sep="\t")
