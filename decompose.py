import numpy as np
from numba import jit

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# This file contains a set of functions to modify and decompose the       #
# symplectic matrices generated by symplectic.py                          #
# Some of the functions are also used to compute                          #
# the collision_probability in chp_py                                     #
# DO NOT MODIFY (unless you have a deep understanding of the code)        #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


def transform_symplectic(S):
    """
    Given a symplectic matrix S that is symplectic with
    L = direct_sum_{j=1}^n X
    Returns a matrix that is symplectic with
    L = [[0, I], [I, 0]] , which corresponds to a valid stabilizer state
    """
    # Initialize some variables
    n = S.shape[0] // 2

    # Find a, b, c, d
    a = np.zeros((n, n), dtype=np.int8)
    b = np.zeros((n, n), dtype=np.int8)
    c = np.zeros((n, n), dtype=np.int8)
    d = np.zeros((n, n), dtype=np.int8)

    # According to the formula in the paper
    for j in range(n):
        for k in range(n):
            a[j, k] = S[(2 * k), (2 * j)]
            b[j, k] = S[((2 * k) + 1), (2 * j)]
            c[j, k] = S[(2 * k), ((2 * j) + 1)]
            d[j, k] = S[((2 * k) + 1), ((2 * j) + 1)]

    # Combine into a final matrix
    top = np.hstack((a, b))
    bottom = np.hstack((c, d))
    S_transformed = np.vstack((top, bottom))

    return S_transformed


def symplectic_to_matrix(S, n, qubits):
    """
    Converts a 2m x 2m symplectic matrix S that is symplectic to a
    2n x 2n matrix that can be matrix multiplied to our state
    NOTE: this has the same effect as decomposing S into a set of
    {C, H, P} gates and then applying those to the state
    Inputs: S = 2m x 2m symplectic matrix that is symplectic with
                L = [[0, I], [I, 0]]
            n = number of qubits in the actual simulation
            qubits = a list of qubits to apply S to
    """

    # Initialize some variables
    M = np.identity(2 * n, dtype=np.int8)
    m = len(qubits)

    # This is a bit confusing but essentially
    # (i, j) in S -> (qubits[i], qubits[j]) in M
    # and x + m in S -> qubits[x] + n in M
    for i, q_i in enumerate(qubits):
        for j, q_j in enumerate(qubits):
            M[q_i, q_j] = S[i, j]
            M[q_i + n, q_j] = S[i + m, j]
            M[q_i, q_j + n] = S[i, j + m]
            M[q_i + n, q_j + n] = S[i + m, j + m]

    return M


def col_wise_gaussian_elimination_steps(A):
    """
    Returns the steps corresponding to a list of CNOT gates that will
    perform Gaussian elimination on F_2 on the matrix A, so that A -> I
    NOTE: this has only been tested to work on a full rank n x n matrix
    """

    # Initialize some variables
    M = np.copy(A)
    n = M.shape[0]
    steps = []

    # First make the matrix lower triangular
    for i in range(n):
        # Make sure we have a 1 in the pivot column
        if M[i, i] != 1:
            for j in range(i + 1, n):
                if M[i, j] == 1:
                    M[:, i] = (M[:, i] + M[:, j]) % 2
                    steps.append((j, i))
                    break

        # Next clear out right side of row i
        for j in range(i + 1, n):
            if M[i, j] == 1:
                M[:, j] = (M[:, j] + M[:, i]) % 2
                steps.append((i, j))

    # Now make bottom left all zeros, so final matrix
    # is the identity
    for i in range(n - 1, -1, -1):
        # Clear out the left side of row i
        for j in range(i - 1, -1, -1):
            if M[i, j] == 1:
                M[:, j] = (M[:, j] + M[:, i]) % 2
                steps.append((i, j))

    return steps


def get_rank(A):
    """
    Gets rank of matrix A using row gaussian elimination on F_2
    NOTE: this has only been test to work on an n x m matrix with n <= m
    """
    # Ranks is the the number of pivots we find
    return len(row_wise_gaussian_elimination_pivots(A))


def find_M(A):
    """
    From Lemma 7 in Aaronson's paper
    Finds M inductively such that A + L = (M)(M^T) where L is diagonal
    """
    n = A.shape[0]
    M = np.identity(n, dtype=np.int8)

    for j in range(n):
        for i in range(j + 1, n):
            s = sum(M[i, k] * M[j, k] for k in range(j))
            M[i, j] = (A[i, j] - s) % 2

    return M


def get_hadamard_steps(c, d):
    """
    From Lemma 6 of Arronson's paper
    Uses row additions to figure out which qubits to apply hadamards to
    in order to make c a full rank matrix
    """
    # Put c and d into an n x 2n matrix
    M = np.hstack((c, d))
    n, m = M.shape
    # Next, perform guassian elimination and return a subset of the
    # pivot columns that are on the right half of the matrix
    # see paper for proof/details
    pivots = row_wise_gaussian_elimination_pivots(M)
    pivot_cols = [j - n for (i, j) in pivots if j >= n]
    return(pivot_cols)


@jit
def row_wise_gaussian_elimination_pivots(A):
    """
    Performs guassian elimination over F_2 on the given matrix A using
    row operations rather than column operations
    NOTE: this has only been test to work on an n x m matrix with n <= m
    Returns: a list of pivots in the REF of matrix A
    """

    # Initialize some variables
    M = np.copy(A)
    n, m = M.shape
    pivots = []

    # Gaussian Elimination using row operations
    # k keeps track of what row we are on
    k = 0
    for j in range(m):
        # If we reached the last row, then stop
        if k == n:
            break

        # Otherwise, find the next pivot, if we do not find one
        # we just move over one column
        if M[k, j] == 1:
            found_pivot = True
        else:
            found_pivot = False
            for i in range(k + 1, n):
                if M[i, j] == 1:
                    found_pivot = True
                    M[k, :] = (M[k, :] + M[i, :]) % 2
                    break

        # If we found a pivot, eliminate the rows beneath it
        # and then increment k
        if found_pivot:
            pivots.append((k, j))
            for i in range(k + 1, n):
                if M[i, j] == 1:
                    M[i, :] = (M[i, :] + M[k, :]) % 2
            k += 1

    return pivots


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# NOTE: we must add this line here so that whenever we import decompose,  #
#       it will compile the gaussian elimination with numba               #
#       otherwise, the parallel map from Pool will NOT use numba          #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
row_wise_gaussian_elimination_pivots(np.identity(2))


def decompose_state(sim):
    """
    Decomposes the sim.state of a chp_py.CHP_Simulation into a set of {C, H, P}
    gates using the algorithm described in
    https://arxiv.org/pdf/quant-ph/0406196.pdf
    Returns a list of tuples of the form (gate, q_1, q_2)
    """

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 0: Initialize some varibles, by convention we will have the state  #
    #         broken up into a block matrix of the form                       #
    #         [[ a, b]                                                        #
    #          [ c, d]]                                                       #
    #         NOTE: a, b, c, d, are aliases for different parts of            #
    #               state matrix, so do NOT modify them only use them to read #
    #               up to date information about the state                    #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    gates = []
    n = sim.state.shape[0] // 2
    a = sim.state[0:n, 0:n]
    b = sim.state[0:n, n:2 * n]
    c = sim.state[n:2 * n, 0:n]
    d = sim.state[n:2 * n, n:2 * n]

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 1: Use Hadamard gates to make c full rank                          #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    steps = get_hadamard_steps(c, d)
    for i in steps:
        sim.apply_hadamard(i)
        gates.append(('h', i, None))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 2: Use CNOT gates to do guassian elimination on c -> I             #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    steps = col_wise_gaussian_elimination_steps(c)
    for (i, j) in steps:
        sim.apply_cnot(i, j)
        gates.append(('c', i, j))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 3: Use Phase gates to add a diagonal matrix to d                   #
    #         NOTE: The inverse of a Phase P is P^3, the inverse of P^2 is    #
    #               P^2 because P^4 = I                                       #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    M = find_M(d)
    L = ((M @ M.T) - d) % 2

    for i in range(n):
        if L[i, i] == 1:
            sim.apply_phase(i)
            gates.append(('p', i, None))
            gates.append(('p', i, None))
            gates.append(('p', i, None))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 4: Use CNOT gates to make c -> M and d -> M                        #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    for j in range(n):
        for i in range(j + 1, n):
            if M[i, j] == 1:
                sim.apply_cnot(i, j)
                gates.append(('c', i, j))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 5: Use Phase gates to make d -> 0 and r_2 -> 0                     #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    for i in range(n):
        sim.apply_phase(i)
        gates.append(('p', i, None))
        gates.append(('p', i, None))
        gates.append(('p', i, None))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 6: Use CNOT gates for guassian elimination so c -> I               #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    steps = col_wise_gaussian_elimination_steps(c)
    for (i, j) in steps:
        sim.apply_cnot(i, j)
        gates.append(('c', i, j))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 7: Use Hadamard gates to make c -> 0 and d -> I                    #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    for i in range(n):
        sim.apply_hadamard(i)
        gates.append(('h', i, None))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 8: Use Phase gates to add a diagonal matrix to b                   #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    M = find_M(b)
    L = ((M @ M.T) - b) % 2

    for i in range(n):
        if L[i, i] == 1:
            sim.apply_phase(i)
            gates.append(('p', i, None))
            gates.append(('p', i, None))
            gates.append(('p', i, None))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 9: Use CNOT gates to make a -> M and b ->  M                       #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    for j in range(n):
        for i in range(j + 1, n):
            if M[i, j] == 1:
                sim.apply_cnot(i, j)
                gates.append(('c', i, j))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 10: Use Phase gates to make b -> 0 and r_1 -> 0                    #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    for i in range(n):
        sim.apply_phase(i)
        gates.append(('p', i, None))
        gates.append(('p', i, None))
        gates.append(('p', i, None))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 11: Use CNOT gates for gaussian elimintation so a -> I and c -> I  #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    steps = col_wise_gaussian_elimination_steps(a)
    for (i, j) in steps:
        sim.apply_cnot(i, j)
        gates.append(('c', i, j))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Step 12: Reverse and return the set of gates                            #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    gates.reverse()
    return gates


def change_gates(gates, qubits):
    """
    Modifies the gates outputted from decompose_state so that they
    apply to the qubits in the list qubits
    Specifically, a gate applied to (i, j) will now apply to
    (qubits[i], qubits[j]
    """
    return [(gate, qubits[i], qubits[j]) if j is not None else
            (gate, qubits[i], None) for (gate, i, j) in gates]


def apply_gates(gates, sim):
    """
    Applies the set of gates to the CHP_Simulation sim where
    gates is a list of tuples of the form (gate, q_1, q_2)
    If verbose is True, it will return the results from the measurements
    of the qubits, otherwise returns None
    """
    for (gate, q1, q2) in gates:
        if gate == 'c':
            sim.apply_cnot(q1, q2)
        elif gate == 'h':
            sim.apply_hadamard(q1)
        elif gate == 'p':
            sim.apply_phase(q1)
        elif gate == 'z':
            sim.apply_z(q1)
        elif gate == 'x':
            sim.apply_x(q1)
        elif gate == 'y':
            sim.apply_y(q1)
        else:
            raise ValueError(
                "gate type must be in {'c', 'h', 'p', 'z', 'x', 'y'}")
