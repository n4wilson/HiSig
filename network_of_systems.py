import argparse
import pandas as pd
from ddot import *
import seaborn as sns
import networkx as nx
from myutils import *


def selected_system_diagram(ontf, df, key, used_cols, genes=None):
    '''
    '''
    ont = Ontology.from_table(ontf, clixo_format=True, is_mapping=lambda x: x[2] == True)
    if len(ont.get_roots()) > 1:
        ont.add_root('ROOT', inplace=True)
    ont.propagate('forward', inplace=True)
    chosen_terms = df[key].tolist()

    ont_sel = ont.delete(to_keep=chosen_terms +['ROOT']+ ont.genes)
    G = ont_sel.to_NdexGraph(layout='bubble')
    mapping = {}
    for n in G.nodes(data=True):
        if (n[1]['NodeType'] == 'Gene') and ((n[1]['Label'] in genes)==False):
            G.remove_node(n[0])
        mapping[n[0]] = n[1]['Label']
    H = nx.relabel_nodes(G, mapping)


    # add node attributes
    df2 = df.set_index(key)
    for c in used_cols:
        if c != key:
            nx.set_node_attributes(H, c, df2[c].to_dict())
    return H


par = argparse.ArgumentParser()
par.add_argument('--input', required=True, help='dataframe, same format to the output of parse.py')
par.add_argument('--node_attr', help='a dataframe with all the other information of systems')
par.add_argument('--join', default='System_name', help='use this string to join the two dataframe')
par.add_argument('--exclude', default=[], nargs='*', help='if specified, excluding certain systems from netwokrs')
par.add_argument('--ont', required=True, help='the hierarchy 3-col file')
par.add_argument('--genes', default=[], help='a string of gene symbols separated by comma')
par.add_argument('--gene_attr', help='a dataframe with gene attributes')
par.add_argument('--name', required=True, help='name for the NDEx network')
args = par.parse_args()

if __name__ == "__main__":
    serv, usr, passwd = ndex_login('http://www.ndexbio.org')
    ont = Ontology.from_table(args.ont,
                              is_mapping=lambda x:x[2]=='gene', clixo_format=True)
    if not 'ROOT' in ont.terms:
        ont.add_root('ROOT', inplace=True)

    df_use = pd.read_table(args.input, sep='\t')
    df_node = pd.read_table(args.node_attr, sep='\t')
    # remove the redundant columns
    df_use = df_use[[c for c in df_use.columns.tolist() if (c==args.join) or (not c in df_node.columns.tolist())]]

    assert args.join in df_use.columns.tolist()
    assert args.join in df_node.columns.tolist()

    terms = df_use[args.join].tolist()

    # add auxiliary nodes
    ont_conn = ont.connected(ont.terms)
    records = []
    ind_sel_terms = np.array([ont.terms.index(t) for t in terms])
    for ti in range(len(ont.terms)):
        x = np.sum(ont_conn[ind_sel_terms, ti])
        if (x> 1) and (not ont.terms[ti] in terms):
            records.append([ont.terms[ti], x])

    df_ancestor = pd.DataFrame(records)
    df_ancestor.sort_values(by=1, ascending=False, inplace=True)
    df_ancestor = df_ancestor.loc[(df_ancestor[0] != 'ROOT') & (df_ancestor[0].isin(args.exclude) == False), :]
    df_ancestor = df_ancestor[[0]]
    df_ancestor.rename(columns = {0:'System_name'}, inplace=True)

    for c in df_use.columns:
        if not c in df_use.columns:
            if (df_use[c].dtype == 'int64') or (df_use[c].dtype == 'float64'):
                df_use[c] = -1
            else:
                df_use[c] = ''

    df_use = pd.concat([df_use, df_ancestor])
    df_use.reset_index(inplace=True, drop=True)

    df_use = df_use.merge(df_node, how='left', left_on =args.join,right_on=args.join)

    # add enhanced graph (for RBVI)
    df_combined_eh = df_use.copy()
    cols_q = [c for c in df_use.columns.tolist() if c.endswith('-q')]
    df_combined_eh['logSize'] = np.log2(df_combined_eh['Size'])

    color_hex = sns.color_palette("Set1", len(cols_q)).as_hex()

    for c in cols_q:
        ct = c.replace('-q', '')
        df_combined_eh[ct.upper() + '_graphvalue'] = 0

    dict_chart_q, dict_chart_mut, dict_chart_mutcnv = {}, {}, {}

    for i, row in df_combined_eh.iterrows():
        attr_list = []
        color_list = []
        label_list_q = []
        label_list_mut = []
        # label_list_mutcnv = []
        sig = 0
        for k in range(len(cols_q)):
            if row[cols_q[k]] > 0:
                ct = cols_q[k].replace('-q', '')
                df_combined_eh.loc[i, ct.upper() + '_graphvalue'] = 1
                attr_list.append(ct.upper() + '_graphvalue')
                color_list.append(color_hex[k])
                label_list_q.append(ct + ' ' + str(row[cols_q[k]]))  # why not show frequencies as label
                label_list_mut.append(ct + ' ' + str(row[ct + '_mut']))  # why not show frequencies as label
                # label_list_mutcnv.append(ct + '_' + str(row[ct.lower() + '_mutcnv']))  # why not show frequencies as label
                sig = 1

        chart_str_q = 'piechart: attributelist="{}" colorlist="{}" labellist="{}" showlabels=True'.format(
            ','.join(attr_list),
            ','.join(color_list),
            ','.join(label_list_q))
        chart_str_mut = 'piechart: attributelist="{}" colorlist="{}" labellist="{}" showlabels=True'.format(
            ','.join(attr_list),
            ','.join(color_list),
            ','.join(label_list_mut))
        # chart_str_mutcnv = 'piechart: attributelist="{}" colorlist="{}" labellist="{}" showlabels=True'.format(
        #     ','.join(attr_list),
        #     ','.join(color_list),
        #     ','.join(label_list_mutcnv))
        if sig:
            dict_chart_q[i] = chart_str_q
            dict_chart_mut[i] = chart_str_mut
            # dict_chart_mutcnv[i] = chart_str_mutcnv

    df_combined_eh['Chart q'] = pd.Series(dict_chart_q)
    df_combined_eh['Chart mut'] = pd.Series(dict_chart_mut)
    # df_combined_eh['Chart mutcnv'] = pd.Series(dict_chart_mutcnv)

    df_combined_eh = df_combined_eh.loc[df_combined_eh[args.join].isin(args.exclude) ==False, :]
    df_combined_eh = df_combined_eh.round(3)

    if args.gene_attr != None:
        df_gene_attr = pd.read_table(args.gene_attr, index_col=0)
        df_gene_attr.reset_index()
        df_gene_attr.rename(columns={'Unnamed: 0':'System_name'}, inplace=True)
        df_gene_attr = df_gene_attr[[c for c in df_gene_attr.columns.tolist() if c in df_combined_eh.columns.tolist()]]
        df_combined_eh = pd.concat([df_combined_eh, df_gene_attr])

    # finally, upload to NDEx
    G =selected_system_diagram(args.ont, df_combined_eh, 'System_name', df_combined_eh.columns.tolist(), args.genes)
    Gnx = nx_to_NdexGraph(G)

    Gnx.set_name(args.name)

    cx = Gnx.to_cx()
    counter = 0
    for entry in cx:
        if 'nodeAttributes' in entry:
            for subentry in entry['nodeAttributes']:
                if 'd' in subentry and subentry['d'] == 'unknown':
                    subentry['d'] = 'double'
                    counter = counter + 1

    G = NdexGraph(cx=cx)

    G.upload_to(serv, usr, passwd)
