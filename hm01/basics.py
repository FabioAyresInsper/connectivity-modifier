from __future__ import annotations
from dataclasses import dataclass
import logging
import networkit as nk
from typing import Iterator, List, Tuple
import os
from . import mincut
from .context import context
from structlog import get_logger
from functools import cache

log = get_logger()
class Graph:
    """Wrapped graph over a networkit graph with an ID label"""
    def __init__(self, data, index):
        self.data = data # nk graph
        self.index = index
        self.construct_hydrator()
    
    @staticmethod
    def from_nk(graph, index = ""):
        """Create a wrapped graph from a networkit graph"""
        return Graph(graph, index)
    
    @staticmethod
    def from_edgelist(path):
        """Read a graph from an edgelist file"""
        edgelist_reader = nk.graphio.EdgeListReader("\t", 0)
        nk_graph = edgelist_reader.read(path)
        return Graph.from_nk(nk_graph)

    def n(self):
        """Number of nodes"""
        return self.data.numberOfNodes()
    
    def m(self):
        """Number of edges"""
        return self.data.numberOfEdges()
    
    @cache
    def mcd(self):
        return min(self.data.degree(n) for n in self.data.iterNodes())
    
    def find_clusters(self, clusterer) -> Iterator[IntangibleSubgraph]:
        """Find clusters using the given clusterer"""
        log.info(f"Finding clusters using clusterer", id = self.index, n = self.n(), m = self.m(), clusterer = clusterer)
        return clusterer.cluster(self)
    
    def find_mincut(self):
        """Find a mincut wrapped over Viecut"""
        return mincut.viecut(self)
    
    def cut_by_mincut(self, mincut_res) -> Tuple[Graph, Graph]:
        """Cut the graph by the mincut result"""
        light = self.induced_subgraph(mincut_res.light_partition, "a")
        heavy = self.induced_subgraph(mincut_res.heavy_partition, "b")
        return light, heavy

    def construct_hydrator(self):
        """Hydrator: a mapping from the compacted id to the original id"""
        n = self.n()
        hydrator = [0] * n
        continuous_ids = nk.graphtools.getContinuousNodeIds(self.data).items()
        assert len(continuous_ids) == n
        for old_id, new_id in continuous_ids:
            hydrator[new_id] = old_id
        self.hydrator = hydrator

    def induced_subgraph(self, ids, suffix):
        assert suffix != "", "Suffix cannot be empty"
        data = nk.graphtools.subgraphFromNodes(self.data, ids)
        index = self.index + suffix
        return Graph(data, index)
    
    def induced_subgraph_from_compact(self, ids, suffix):
        return self.induced_subgraph([self.hydrator[i] for i in ids], suffix)
    
    def intangible_subgraph(self, nodes, suffix):
        return IntangibleSubgraph(nodes, self.index + suffix)

    def intangible_subgraph_from_compact(self, ids, suffix):
        return self.intangible_subgraph([self.hydrator[i] for i in ids], suffix)
    
    def as_compact_edgelist_filepath(self):
        """Get a filepath to the graph as a compact/continuous edgelist file"""
        p = context.request_graph_related_path(self, "edgelist")
        nk.graphio.writeGraph(self.data, p, nk.Format.EdgeListSpaceOne)
        return p

    def as_metis_filepath(self):
        """Get a filepath to the graph to a (continuous) METIS file"""
        p = context.request_graph_related_path(self, "metis")
        nk.graphio.writeGraph(self.data, p, nk.Format.METIS)
        return p
    
    def nodes(self):
        """Iterate over the nodes"""
        return self.data.iterNodes()
    
    @staticmethod
    def from_space_edgelist(filepath: str, index=""):
        return Graph(nk.graphio.readGraph(filepath, nk.Format.EdgeListSpaceZero), index)

    @staticmethod
    def from_erdos_renyi(n, p, index=""):
        return Graph(nk.generators.ErdosRenyiGenerator(n, p).generate(), index)
    
    def to_intangible(self, graph):
        return IntangibleSubgraph(list(self.nodes()), self.index)
    
    def to_igraph(self):
        import igraph as ig
        cont_ids = nk.graphtools.getContinuousNodeIds(self.data)
        compact_graph = nk.graphtools.getCompactedGraph(self.data, cont_ids)
        edges = [(u, v) for u, v in compact_graph.iterEdges()]
        return ig.Graph(self.n(), edges)

@dataclass
class IntangibleSubgraph():
    """A yet to be realized subgraph, containing only the node ids"""
    nodes : List[int]
    index : str

    def realize(self, graph : Graph) -> Graph:
        """Realize the subgraph"""
        return graph.induced_subgraph(self.nodes, self.index)

    def __len__(self):
        return len(self.nodes)
    
    def n(self):
        return len(self)