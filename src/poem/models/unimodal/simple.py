# -*- coding: utf-8 -*-

"""Implementation of SimplE."""

from typing import Optional

import torch
import torch.autograd
from torch import nn

from poem.constants import GPU
from poem.instance_creation_factories.triples_factory import TriplesFactory
from poem.models.base import BaseModule
from poem.utils import slice_triples

__all__ = ['SimplE']


class SimplE(BaseModule):
    """An implementation of SimplE [kazemi2018]_.

    This model extends CP by updating a triple, and the inverse triple.

    .. [kazemi2018] S. M. Kazemi, D. Poole (2018). `SimplE Embedding for Link Prediction in Knowledge Graphs` <https://papers.nips.cc/paper/7682-simple-embedding-for-link-prediction-in-knowledge-graphs>_. NIPS'18

    .. seealso::

       - Official implementation: https://github.com/Mehran-k/SimplE
       - Improved implementation in pytorch: https://github.com/baharefatemi/SimplE
    """

    margin_ranking_loss_size_average: bool = True

    def __init__(
            self,
            triples_factory: TriplesFactory,
            embedding_dim: int = 200,
            criterion: nn.modules.loss = nn.MarginRankingLoss(margin=1., reduction='mean'),
            preferred_device: str = GPU,
            random_seed: Optional[int] = None,
    ) -> None:
        super().__init__(
            triples_factory=triples_factory,
            embedding_dim=embedding_dim,
            criterion=criterion,
            preferred_device=preferred_device,
            random_seed=random_seed,
        )
        self.relation_embeddings = None

        self._init_embeddings()

    def _init_embeddings(self):
        super()._init_embeddings()
        self.tail_entity_embeddings = nn.Embedding(self.num_entities, self.embedding_dim)
        self.relation_embeddings = nn.Embedding(self.num_relations, self.embedding_dim)
        self.inverse_relation_embeddings = nn.Embedding(self.num_relations, self.embedding_dim)

    def forward_owa(
            self,
            batch: torch.tensor,
    ):
        # Split triple in head, relation, tail
        h_ind, r_ind, t_ind = slice_triples(batch)

        # Lookup embeddings
        hh = self.entity_embeddings(h_ind)
        ht = self.entity_embeddings(t_ind)
        th = self.tail_entity_embeddings(h_ind)
        tt = self.tail_entity_embeddings(t_ind)
        r = self.relation_embeddings(r_ind)
        r_inv = self.inverse_relation_embeddings(r_ind)

        # Compute CP scores for triple, and inverse triple
        score = torch.sum(hh * r * tt, dim=-1)
        inverse_score = torch.sum(ht * r_inv * th, dim=-1)

        # Final score is average
        scores = 0.5 * (score + inverse_score)

        # Note: In the code in their repository, the score is clamped to [-20, 20].
        #       That is not mentioned in the paper, so it is omitted here.

        return scores

    def forward_cwa(
            self,
            batch: torch.tensor,
    ) -> torch.tensor:
        h_ind = batch[:, 0]
        r_ind = batch[:, 1]

        # Lookup embeddings
        hh = self.entity_embeddings(h_ind)
        th = self.tail_entity_embeddings(h_ind)
        r = self.relation_embeddings(r_ind)
        r_inv = self.inverse_relation_embeddings(r_ind)
        ht = self.entity_embeddings.weight
        tt = self.tail_entity_embeddings.weight

        # Compute CP scores for triple, and inverse triple
        score = torch.sum(hh[:, None, :] * r[:, None, :] * tt[None, :, :], dim=-1)
        inverse_score = torch.sum(ht[None, :, :] * r_inv[:, None, :] * th[:, None, :], dim=-1)

        # Final score is average
        scores = 0.5 * (score + inverse_score)

        return scores

    def forward_inverse_cwa(
            self,
            batch: torch.tensor,
    ) -> torch.tensor:
        r_ind = batch[:, 0]
        t_ind = batch[:, 1]

        # Lookup embeddings
        hh = self.entity_embeddings.weight
        ht = self.entity_embeddings(t_ind)
        th = self.tail_entity_embeddings.weight
        tt = self.tail_entity_embeddings(t_ind)
        r = self.relation_embeddings(r_ind)
        r_inv = self.inverse_relation_embeddings(r_ind)

        # Compute CP scores for triple, and inverse triple
        score = torch.sum(hh[None, :, :] * r[:, None, :] * tt[:, None, :], dim=-1)
        inverse_score = torch.sum(ht[:, None, :] * r_inv[:, None, :] * th[None, :, :], dim=-1)

        # Final score is average
        scores = 0.5 * (score + inverse_score)

        # Note: In the code in their repository, the score is clamped to [-20, 20].
        #       That is not mentioned in the paper, so it is omitted here.

        return scores
