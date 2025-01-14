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

import numpy as np
import scipy.special
import torch


def gaussian(x, mu, var):
    return -0.5 * (float(np.log(2 * np.pi)) + torch.log(var) + (mu-x)**2/var)


def lognormal(x, mu, var):
    lnx = torch.log(x)
    return gaussian(lnx, mu, var) - lnx


def bernoulli(p, y):
    return torch.log(y*p+(1-y)*(1-p))


def gammaln(x):
    # attention: Not differentiable!
    if np.isscalar(x):
        y = float(scipy.special.gammaln(x))
    elif isinstance(x, torch.Tensor):
        y = torch.as_tensor(scipy.special.gammaln(x.numpy()), dtype=x.dtype)
    else:
        raise ValueError("Unsupported input type "+str(type(x)))
    return y


def poisson(lamb, y):
    return y * torch.log(lamb) - lamb - gammaln(y + 1.)


def exponential(lamb, y):
    return - y/lamb - torch.log(lamb)


def gamma(shape, scale, x):
    return (-shape * torch.log(scale) - gammaln(shape)
            + (shape - 1.) * torch.log(x) - x / scale)


def beta(alpha, beta, y):
    # need to clip y, since log of 0 is nan...
    y = torch.clamp(y, min=1e-6, max=1-1e-6)
    return ((alpha - 1.) * torch.log(y) + (beta - 1.) * torch.log(1. - y)
            + gammaln(alpha + beta)
            - gammaln(alpha)
            - gammaln(beta))


def laplace(mu, sigma, y):
    return - torch.abs(mu - y) / sigma - torch.log(2. * sigma)


def multivariate_normal(x, mu, L):
    """
    L is the Cholesky decomposition of the covariance.
    x and mu are either vectors (ndim=1) or matrices. In the matrix case, we
    assume independence over the *columns*: the number of rows must match the
    size of L.
    """
    d = x - mu
    if d.dim() == 1:
        d = d.unsqueeze(1)
    alpha, _ = torch.linalg.solve_triangular(L, d, upper=False)
    alpha = alpha.squeeze(1)
    num_col = 1 if x.dim() == 1 else x.size(1)
    num_dims = x.size(0)
    ret = - 0.5 * num_dims * num_col * float(np.log(2 * np.pi))
    ret += - num_col * torch.diag(L).log().sum()
    ret += - 0.5 * (alpha**2).sum()
    # ret = - 0.5 * (alpha**2).mean()
    return ret
