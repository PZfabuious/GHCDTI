import torch
import torch.nn as nn


class Contrast(nn.Module):
    def __init__(self, out_dim, tau, keys, num_hierarchies=2):
        super(Contrast, self).__init__()
        self.tau = tau
        self.num_hierarchies = num_hierarchies
        self.proj = nn.ModuleDict({
            k: nn.ModuleList([
                nn.Sequential(
                    nn.Linear(out_dim, out_dim),
                    nn.ELU(),
                    nn.Linear(out_dim, out_dim)
                ) for _ in range(num_hierarchies)
            ]) for k in keys
        })
        for k, v in self.proj.items():
            for hierarchy in v:
                for layer in hierarchy:
                    if isinstance(layer, nn.Linear):
                        nn.init.xavier_normal_(layer.weight, gain=1.414)

    def sim(self, z1, z2):
        z1_norm = torch.norm(z1, dim=-1, keepdim=True)
        z2_norm = torch.norm(z2, dim=-1, keepdim=True)
        dot_numerator = torch.mm(z1, z2.t())
        dot_denominator = torch.mm(z1_norm, z2_norm.t())
        sim_matrix = torch.exp(dot_numerator / dot_denominator / self.tau)
        return sim_matrix

    def compute_loss(self, z_mp, z_sc, pos, k):
        total_loss = 0
        for hierarchy in range(self.num_hierarchies):
            z_proj_mp = self.proj[k][hierarchy](z_mp)
            z_proj_sc = self.proj[k][hierarchy](z_sc)

            matrix_mp2sc = self.sim(z_proj_mp, z_proj_sc)
            matrix_sc2mp = matrix_mp2sc.t()

            matrix_mp2sc = matrix_mp2sc / (torch.sum(matrix_mp2sc, dim=1).view(-1, 1) + 1e-8)
            lori_mp = -torch.log(matrix_mp2sc.mul(pos.to_dense()).sum(dim=-1)).mean()

            matrix_sc2mp = matrix_sc2mp / (torch.sum(matrix_sc2mp, dim=1).view(-1, 1) + 1e-8)
            lori_sc = -torch.log(matrix_sc2mp.mul(pos.to_dense()).sum(dim=-1)).mean()

            total_loss += lori_mp + lori_sc
        return total_loss

    def forward(self, z_mp, z_sc, pos):
        sum_loss = 0
        for k in pos.keys():
            sum_loss += self.compute_loss(z_mp[k], z_sc[k], pos[k], k)
        return sum_loss

