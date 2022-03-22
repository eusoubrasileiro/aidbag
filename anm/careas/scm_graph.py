import networkx as nx
import matplotlib.pyplot as plt
import copy, numpy as np 
import random 
from .scm_util import comparePnames

def hierarchy_pos(G, root=None, width=1., vert_gap = 0.2, vert_loc = 0, xcenter = 0.5):
    """
    From Joel's answer at https://stackoverflow.com/a/29597209/2966723.  
    Licensed under Creative Commons Attribution-Share Alike 
    
    If the graph is a tree this will return the positions to plot this in a 
    hierarchical layout.
    
    G: the graph (must be a tree)
    
    root: the root node of current branch 
    - if the tree is directed and this is not given, 
      the root will be found and used
    - if the tree is directed and this is given, then 
      the positions will be just for the descendants of this node.
    - if the tree is undirected and not given, 
      then a random choice will be used.
    
    width: horizontal space allocated for this branch - avoids overlap with other branches
    
    vert_gap: gap between levels of hierarchy
    
    vert_loc: vertical location of root
    
    xcenter: horizontal location of root
    """
    if not nx.is_tree(G):
        raise TypeError('cannot use hierarchy_pos on a graph that is not a tree')

    if root is None:
        if isinstance(G, nx.DiGraph):
            root = next(iter(nx.topological_sort(G)))  #allows back compatibility with nx version 1.11
        else:
            root = random.choice(list(G.nodes))

    def _hierarchy_pos(G, root, width=1., vert_gap = 0.2, vert_loc = 0, xcenter = 0.5, pos = None, parent = None):
        """
        see hierarchy_pos docstring for most arguments

        pos: a dict saying where all nodes go if they have been assigned
        parent: parent of this branch. - only affects it if non-directed
        """    
        if pos is None:
            pos = {root:(xcenter,vert_loc)}
        else:
            pos[root] = (xcenter, vert_loc)
        children = list(G.neighbors(root))
        if not isinstance(G, nx.DiGraph) and parent is not None:
            children.remove(parent)  
        if len(children)!=0:
            dx = width/len(children) 
            nextx = xcenter - width/2 - dx/2
            for child in children:
                nextx += dx
                pos = _hierarchy_pos(G,child, width = dx, vert_gap = vert_gap, 
                                    vert_loc = vert_loc-vert_gap, xcenter=nextx,
                                    pos=pos, parent = root)
        return pos

    return _hierarchy_pos(G, root, width, vert_gap, vert_loc, xcenter)


def GraphAddEdges(process, G, ignore=''):
    """ *ignore : to avoid infinit-loop also builds outward"""
    associados = copy.copy(process.Associados)
    data = copy.copy(process.AssociadosData)    
    if ignore in associados:
        del associados[ignore]
        del data[ignore]
    G.add_edges_from([(process.name, associado, data[associado]) for associado in associados.keys()])
    for associado in associados.values():
        GraphAddEdges(associado, G, process.name)

def DrawGraphAssociados(G):
    # compare process to get older to create node sizes?    
    sortedNodes = sorted(list(G.nodes), key=cmp_to_key(comparePnames), reverse=True)
    sizes = np.geomspace(100, 600,num=len(sortedNodes), dtype=int) # better sizes than limspace
    node_sizes = { k:v for k,v in zip(sortedNodes, sizes) }

    pos = nx.spring_layout(G, seed=150)
    plt.figure(figsize=(9,9))
    nx.draw(G, pos, 
        node_size=[node_sizes[node] for node in G.nodes], 
        with_labels=True)
    ax = plt.gca()
    ax.margins(0.05)
    # instead of two labels merge them with a new line 
    labels = { (na, nb) : attr['tipo']+'\n'+attr['data'].strftime('%d/%m/%Y')
        for na, nb, attr in G.edges(data=True) }
    nx.draw_networkx_edge_labels(G, pos, edge_labels=labels)
    plt.axis("off")
    plt.show()

# G = nx.Graph()
# GraphAddEdges(careas.scm.ProcessStorage['832.547/2014'], G)
# DrawGraphAssociados(G)

from functools import cmp_to_key

def DrawGraphAssociadosDirect(G):
    # compare process to get older to create node sizes?    
    sortedNodes = sorted(list(G.nodes), key=cmp_to_key(comparePnames), reverse=True)
    sizes = np.geomspace(100, 600,num=len(sortedNodes), dtype=int) # better sizes than limspace
    node_sizes = { k:v for k,v in zip(sortedNodes, sizes) }

    Gdg = G.to_directed()
    # remove vertices that are not source = older -> target = younger 
    Gd = Gdg.copy()
    for sc, tg in Gdg.edges():
        #print(sc, tg, careas.scm.comparePnames(sc, tg))
        if comparePnames(sc, tg) > 0:
            Gd.remove_edge(sc, tg)
        else: # add_edge only adds a new attribute to it
            Gd.add_edge(sc, tg, weight=1./len(Gdg.out_edges(sc))) # weight used by some plotting options
    #pos = nx.shell_layout(Gd, cclists, rotate=np.pi/10, scale=0.1)
    pos = hierarchy_pos(Gd,sortedNodes[-1]) 
    plt.figure(figsize=(9,9))
    nx.draw(Gd, pos,
        node_size=[node_sizes[node] for node in Gd.nodes], 
        with_labels=True)
    ax = plt.gca()
    ax.margins(0.05)
    #instead of two labels merge them with a new line 
    labels = { (na, nb) : attr['tipo']+'\n'+attr['data'].strftime('%d/%m/%Y')
        for na, nb, attr in Gd.edges(data=True) }
    nx.draw_networkx_edge_labels(Gd, pos, edge_labels=labels, alpha=0.6)
    plt.axis("off")
    plt.show()

#plt.axis("off")
#plt.show()
