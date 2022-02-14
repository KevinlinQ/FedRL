import os
import argparse
import matplotlib as mpl

from utils import *
from tqdm import tqdm

mpl.use('Agg')

parser = argparse.ArgumentParser()
parser.add_argument("--nS", default=5, type=int)
parser.add_argument("--nA", default=5, type=int)
parser.add_argument("--gamma", default=0.9, type=float)
parser.add_argument("--lr", default=1e-2, type=float)
parser.add_argument("--lr_decay", default=0.5, type=float)
parser.add_argument("--n", default=5, type=int)
parser.add_argument("--eps", default=0.05, type=float)
parser.add_argument("--sparsity", default=0.2, type=float)
parser.add_argument("--gen", default="random", type=str)
parser.add_argument("--iter", default=128)
args = parser.parse_args()

nS, nA, gamma = args.nS, args.nA, args.gamma
gen, eps = args.gen, args.eps
ntrain = args.n
ntest = 4 * args.n
sparsity = args.sparsity

d_0 = np.ones(nS) / nS

outer_iter_num = 16000

Seed = 101

E_lst = (1, 2, 4, 8, 16, 32)

E_size = len(E_lst) + 1

separation_len = 50

save_dir = './plot-QAvg-random_MDP'


def experiment():
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    np.random.seed(Seed)
    seeds = np.random.randint(low=0, high=1000000, size=outer_iter_num)

    total_MEObj_lst = np.zeros((outer_iter_num, E_size, args.iter))
    total_test_MEObj_lst = np.zeros((outer_iter_num, E_size, args.iter))

    total_MEObj_base_lst = np.zeros((outer_iter_num, args.iter))  # Baseline
    total_MEObj_base_avg_lst = np.zeros((outer_iter_num, args.iter))  # Baseline2
    total_test_MEObj_base_lst = np.zeros((outer_iter_num, args.iter))  # Baseline
    total_test_MEObj_base_avg_lst = np.zeros((outer_iter_num, args.iter))  # Baseline2

    for count in tqdm(range(outer_iter_num)):
        # Generate environments
        seed = seeds[count]
        R = np.random.uniform(low=0, high=1, size=(nS, nA))
        Q_init = np.random.uniform(size=(nS, nA))
        Ps = generate_Ps(ntrain + ntest, nS, nA, gen=gen, eps=eps, sparsity=sparsity, seed=seed)

        train_P = Ps[:ntrain]
        test_P = Ps[ntrain:]
        MEObj_lst = np.zeros((E_size, args.iter))
        test_MEObj_lst = np.zeros((E_size, args.iter))
        MEObj_base_lst = np.zeros((args.iter))  # Baseline
        MEObj_base_avg_lst = np.zeros((args.iter))  # Baseline2
        test_MEObj_base_lst = np.zeros((args.iter))  # Baseline
        test_MEObj_base_avg_lst = np.zeros((args.iter))  # Baseline2

        # QAvg with different Es
        for E_num in range(E_size-1):
            E = E_lst[E_num]
            Q = Q_init.copy()
            lr = args.lr
            for e in range(args.iter // E):
                # If the decrease is too small or negative, reduce the lr
                if e > 2 and (MEObj_lst[E_num][(e - 1)*E] - MEObj_lst[E_num][(e - 2)*E]) < MEObj_lst[E_num][(e - 2)*E] * 1e-3:
                    lr = lr * args.lr_decay

                V = QtoV(Q)
                pi = QtoPolicy(Q)
                ME_Obj = evaluate_MEObj_from_policy(pi, R, train_P, d_0, gamma)
                ME_Obj_test = evaluate_MEObj_from_policy(pi, R, test_P, d_0, gamma)
                for ttt in range(E):
                    MEObj_lst[E_num][e * E + ttt] = ME_Obj
                    test_MEObj_lst[E_num][e * E + ttt] = ME_Obj_test

                Qs = []
                for i in range(ntrain):
                    Vi = V.copy()
                    for _ in range(E):
                        delta_Vi, _ = value_iteration(Vi, train_P[i], R, gamma)
                        Vi = (1 - lr) * Vi + lr * delta_Vi
                    Qi = VtoQ(Vi, train_P[i], R, gamma)
                    Qs.append(Qi)
                Q = sum(Qs) / ntrain

        # Baseline: Train every agent separately, i.e. do not merge
        lr = args.lr
        Q = Q_init.copy()
        Qs = [Q.copy() for _ in range(ntrain)]
        Q_avg = Q
        for e in range(args.iter):
            if e > 2 and (MEObj_lst[-1][e - 1] - MEObj_lst[-1][e - 2]) < MEObj_lst[-1][e - 2] * 1e-3:
                lr = lr * args.lr_decay

            pi_avg = QtoPolicy(Q_avg)

            ME_Obj = evaluate_MEObj_from_policy(pi_avg, R, train_P, d_0, gamma)
            ME_Obj_test = evaluate_MEObj_from_policy(pi_avg, R, test_P, d_0, gamma)

            MEObj_lst[-1][e] = ME_Obj
            test_MEObj_lst[-1][e] = ME_Obj_test

            for i in range(ntrain):
                Qi = Qs[i]
                Vi = QtoV(Qi)
                delta_Vi, _ = value_iteration(Vi, train_P[i], R, gamma)
                Vi = (1 - lr) * Vi + lr * delta_Vi
                Qi = VtoQ(Vi, train_P[i], R, gamma)
                Qs[i] = Qi
            Q_avg = sum(Qs) / ntrain

            best_ME_Obj = -inf
            best_label = -1
            avg_ME_Obj = 0
            avg_ME_Obj_test = 0
            ME_Obj_tests = []
            for i in range(ntrain):
                Qi = Qs[i]
                pi_i = QtoPolicy(Qi)
                ME_Obj_i = evaluate_MEObj_from_policy(pi_i, R, train_P, d_0, gamma)
                avg_ME_Obj += ME_Obj_i
                if ME_Obj_i > best_ME_Obj:
                    best_ME_Obj = ME_Obj_i
                    best_label = i
                # Test
                ME_Obj_i_test = evaluate_MEObj_from_policy(pi_i, R, test_P, d_0, gamma)
                avg_ME_Obj_test += ME_Obj_i_test
                ME_Obj_tests.append(ME_Obj_i_test)
            MEObj_base_lst[e] = best_ME_Obj
            MEObj_base_avg_lst[e] = avg_ME_Obj / ntrain
            test_MEObj_base_avg_lst[e] = avg_ME_Obj_test / ntrain
            test_MEObj_base_lst[e] = ME_Obj_tests[best_label]
        MEObj_lst = MEObj_lst - 0.5 / (1 - gamma)
        test_MEObj_lst = test_MEObj_lst - 0.5 / (1 - gamma)
        MEObj_base_avg_lst = MEObj_base_avg_lst - 0.5 / (1 - gamma)
        test_MEObj_base_avg_lst = test_MEObj_base_avg_lst - 0.5 / (1 - gamma)
        MEObj_base_lst = MEObj_base_lst - 0.5 / (1 - gamma)
        test_MEObj_base_lst = test_MEObj_base_lst - 0.5 / (1 - gamma)

        total_MEObj_lst[count] = MEObj_lst
        total_MEObj_base_lst[count] = MEObj_base_lst
        total_MEObj_base_avg_lst[count] = MEObj_base_avg_lst
        total_test_MEObj_lst[count] = test_MEObj_lst
        total_test_MEObj_base_lst[count] = test_MEObj_base_lst
        total_test_MEObj_base_avg_lst[count] = test_MEObj_base_avg_lst

    np.save(save_dir + '/MEOBj_lst.npy', total_MEObj_lst)
    np.save(save_dir + '/MEOBj_base_lst.npy', total_MEObj_base_lst)
    np.save(save_dir + '/MEOBj_base_avg_lst.npy', total_MEObj_base_avg_lst)

    np.save(save_dir + '/test_MEOBj_lst.npy', total_test_MEObj_lst)
    np.save(save_dir + '/test_MEOBj_base_lst.npy', total_test_MEObj_base_lst)
    np.save(save_dir + '/test_MEOBj_base_avg_lst.npy', total_test_MEObj_base_avg_lst)
    return


def report():
    print('Save dir=' + save_dir)
    coff = np.sqrt(outer_iter_num)
    total_MEOBj_lst = np.load(save_dir + '/MEOBj_lst.npy')
    total_test_MEOBj_lst = np.load(save_dir + '/test_MEOBj_lst.npy')

    for E_num in range(E_size):
        print('-' * separation_len)
        if E_num == E_size - 1:
            print('E=Inf:')
        else:
            print(f'E={E_lst[E_num]}:')
        train_mean = np.max(np.average(total_MEOBj_lst[:, E_num, :], axis=0))
        train_std = np.std(total_MEOBj_lst[:, E_num, :], axis=0)[-1] / coff
        test_mean = np.max(np.average(total_test_MEOBj_lst[:, E_num, :], axis=0))
        test_std = np.std(total_test_MEOBj_lst[:, E_num, :], axis=0)[-1] / coff
        print(f'Train: Mean={train_mean}, Std={train_std}')
        print(f'Test: Mean={test_mean}, Std={test_std}')
    return


if __name__ == '__main__':
    experiment()
    report()
