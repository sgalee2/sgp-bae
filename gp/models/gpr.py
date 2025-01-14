# Copyright 2016 James Hensman, alexggmatthews, PabloLeon, Valentine Svensson
# Copyright 2017 Thomas Viehmann
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import torch

from .. import likelihoods
from .. import densities

from .model import GPModel


class GPR(GPModel):
    """Gaussian Process Regression.

    This is a vanilla implementation of GP regression with a Gaussian
    likelihood.  Multiple columns of Y are treated independently. The log
    likelihood i this models is sometimes referred to as the 'marginal
    log likelihood', and is given by

    \log p(\mathbf y \,|\, \mathbf f) = \mathcal N\left(\mathbf y\,|\, 0, \mathbf K + \sigma_n \mathbf I\right)
    """
    def __init__(self, X, Y, kern, mean_function=None, **kwargs):
        """Initialization

        Args:
            X is a data matrix, size N x D
            Y is a data matrix, size N x R
        """
        likelihood = likelihoods.Gaussian(dtype=X.dtype)
        super(GPR, self).__init__(X, Y, kern, likelihood, mean_function, **kwargs)
        self.num_latent = Y.size(1)

    def compute_log_likelihood(self, X=None, Y=None):
        """Construct function to compute the likelihood.
        """
        # assert X is None and Y is None, "{} does not support minibatch mode".format(str(type(self)))
        if X is None:
            X = self.X
        if Y is None:
            Y = self.Y

        K = self.kern.K(X)
        jitter = self.jitter_level

        if self.likelihood.variance.get() != 0.:
            K = K + torch.eye(X.size(0), dtype=X.dtype, device=X.device) * \
                self.likelihood.variance.get()
        else:
            K = K + torch.eye(X.size(0), dtype=X.dtype, device=X.device) * \
                jitter

        multiplier = 1
        while True:
            try:
                L = torch.cholesky(K + multiplier*jitter, upper=False)
                break
            except RuntimeError as err:
                multiplier *= 2.
                if float(multiplier) == float("inf"):
                    raise RuntimeError("increase to inf jitter")
        m = self.mean_function(X)

        if Y.shape[1] > 1:
            results = []
            for i in range(int(Y.shape[1])):
                results.append(densities.multivariate_normal(
                    Y[:, i].float(), m.float(), L.float()))
            return torch.stack(results)
        else:
            return densities.multivariate_normal(Y, m, L)

    def log_prob(self, X, Y):
        return self.compute_log_likelihood(X, Y)

    def predict_f(self, Xnew, full_cov=False):
        """
        Xnew is a data matrix, point at which we want to predict

        This method computes
            p(F* | Y )

        where F* are points on the GP at Xnew, Y are noisy observations at X.
        """
        Kx = self.kern.K(self.X, Xnew)
        K = self.kern.K(self.X) + torch.eye(self.X.size(0), dtype=self.X.dtype, device=self.X.device) * self.likelihood.variance.get()
        L = torch.cholesky(K, upper=False)

        A = torch.linalg.solve_triangular(L, Kx, upper=False)  # could use triangular solve, note gesv has B first, then A in AX=B
        V = torch.linalg.solve_triangular(L, self.Y - self.mean_function(self.X), upper=False) # could use triangular solve

        fmean = torch.mm(A.t(), V) + self.mean_function(Xnew)
        if full_cov:
            fvar = self.kern.K(Xnew) - torch.mm(A.t(), A)
            fvar = fvar.unsqueeze(2).expand(fvar.size(0), fvar.size(1), self.Y.size(1))
        else:
            fvar = self.kern.Kdiag(Xnew) - (A**2).sum(0)
            fvar = fvar.view(-1, 1)
            fvar = fvar.expand(fvar.size(0), self.Y.size(1))

        return fmean, fvar
