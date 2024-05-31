import sys 
import copy, numpy as np 
import random 
from functools import cmp_to_key
import networkx as nx
import matplotlib.pyplot as plt
from .pud import cmpPud, pud


class pGraph(nx.DiGraph):
    """
    A networkx.Graph of processes and their associados 
    use @threadSafe to avoid concurrent access
    """
    def __init__(self, ebunch_to_add=None):
        """
        Initializes and adds edges (if not None) from a list of edge bunches.        
        Args:
            ebunch_to_add (list, optional): A list of edge bunches to add to the graph. Defaults to None.
            Can come from a pGraph.toList() or JSON deserialized.        
        """        
        super().__init__()
        if ebunch_to_add and isinstance(ebunch_to_add, list):
            self.add_edges_from(ebunch_to_add)            
        
    def toList(self):
        """
        Generates a List of 3-tuples (u, v, d) containing edge data.
        tuple: A tuple containing the source node (u), target node (v), and
                a dictionary (d) of edge data for the edge between u and v.
        Note:
        This should be used to save on a database or to load from a database 
        using JSON serialization.
        """
        return list(self.edges(data=True))


def toChronology(G: pGraph):
    """turn Graph in a Directed Graph respecting chronology order 
    from older (parent) to younger (children) a tree like structure 
    uses `pud` for node comparision
    may raise an exception in case on impossible comparision
    """
    chronoG = pGraph()
    for u, v, d in G.edges(data=True):
        # Compare nodes u and v using the key function
        if pud(u) < pud(v):
            # Add a directed edge u -> v
            chronoG.add_edge(u, v, **d)
        else:
            # Add a directed edge v -> u
            chronoG.add_edge(v, u, **d)
    return chronoG
    

###########################################################
#                       Plotting 
###########################################################


def plotGraph(G, layout=nx.spring_layout, figsize=(9,9)):
    """Plot graph of associados
    Node sizes are giving from older to younger
    Labels are 'tipo' e 'data' da associação"""
    # compare process to get older to create node sizes?    
    sortedNodes = sorted(list(G.nodes), key=cmp_to_key(cmpPud), reverse=False)
    sizes = np.geomspace(100, 600,num=len(sortedNodes), dtype=int) # better sizes than limspace
    node_sizes = { k:v for k,v in zip(sortedNodes, sizes) }
    pos = layout(G)
    plt.figure(figsize=figsize)
    nx.draw(G, pos, 
        node_size=[node_sizes[node] for node in G.nodes], 
        with_labels=True)
    ax = plt.gca()
    ax.margins(0.05)
    # instead of two labels merge them with a new line 
    labels = { (na, nb) : attr['tipo']+'\n'+attr['data-ass'].strftime('%d/%m/%Y')
        for na, nb, attr in G.edges(data=True) }
    nx.draw_networkx_edge_labels(G, pos, edge_labels=labels)
    plt.axis("off")
    plt.show()


def plotDirectGraphAssociados(Gd, root=None):
    """*root: process to use as source of the tree
    default to the oldest"""
    # compare process to get older to create node sizes?    
    sortedNodes = sorted(list(Gd.nodes), key=cmp_to_key(cmpPud))    
    sizes = np.geomspace(100, 600,num=len(sortedNodes), dtype=int) # better sizes than limspace
    node_sizes = { k:v for k,v in zip(sortedNodes, sizes) }
    # uses custom plotting layout bellow 
    if not root:
        root = sortedNodes[0] # oldest
    pos = hierarchy_pos(Gd, root) 
    plt.figure(figsize=(9,9))
    nx.draw(Gd, pos,
        node_size=[node_sizes[node] for node in Gd.nodes], 
        with_labels=True)
    ax = plt.gca()
    ax.margins(0.05)
    #instead of two labels merge them with a new line 
    labels = { (na, nb) : attr['tipo']+'\n'+attr['data-ass'].strftime('%d/%m/%Y')
        for na, nb, attr in Gd.edges(data=True) }
    nx.draw_networkx_edge_labels(Gd, pos, edge_labels=labels, alpha=0.6)
    plt.axis("off")
    plt.show()

# networkx custom plotting layout for tree-like graphs
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