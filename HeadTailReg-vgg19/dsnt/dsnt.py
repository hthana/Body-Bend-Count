import tensorflow as tf
def dsnt(inputs, method='softmax'):
    norm_heatmap = _normalise_heatmap(inputs, method)
    batch_count = tf.shape(norm_heatmap)[0]
    height = tf.shape(norm_heatmap)[1]
    width = tf.shape(norm_heatmap)[2]

    dsnt_x = tf.tile([[(2 * tf.range(1, width+1) - (width + 1)) / width]], [batch_count, height, 1])
    dsnt_x = tf.cast(dsnt_x, tf.float32)
    dsnt_y = tf.tile([[(2 * tf.range(1, height+1) - (height + 1)) / height]], [batch_count, width, 1])
    dsnt_y = tf.cast(tf.transpose(dsnt_y, perm=[0, 2, 1]), tf.float32)

    outputs_x = tf.reduce_sum(tf.multiply(norm_heatmap, dsnt_x), axis=[1, 2])
    outputs_y = tf.reduce_sum(tf.multiply(norm_heatmap, dsnt_y), axis=[1, 2])

    coords_zipped = tf.stack([outputs_x, outputs_y], axis=1)

    return norm_heatmap, coords_zipped

def js_reg_loss(heatmaps, centres, fwhm=1):

    gauss = _make_gaussians(centres, tf.shape(heatmaps)[1], tf.shape(heatmaps)[2], fwhm)

    divergences = _js_2d(heatmaps, gauss)
    return tf.reduce_mean(divergences)


def _normalise_heatmap(inputs, method='softmax'):

    inputs = tf.reshape(inputs, tf.shape(inputs)[:3])

    normalise = lambda x: tf.div(x, tf.reshape(tf.reduce_sum(x, [1, 2]), [2, 1, 1]))

    if method == 'softmax':
        inputs = _softmax2d(inputs, axes=[1, 2])
    elif method == 'abs':
        inputs = tf.abs(inputs)
        inputs = normalise(inputs)
    elif method == 'relu':
        inputs = tf.nn.relu(inputs)
        inputs = normalise(inputs)
    elif method == 'sigmoid':
        inputs = tf.nn.sigmoid(inputs)
        inputs = normalise(inputs)
    else:
        msg = "Unknown rectification method \"{}\"".format(method)
        raise ValueError(msg)
    return inputs

def _kl_2d(p, q, eps=24):
    unsummed_kl = p * (tf.log(p + eps) - tf.log(q + eps))
    kl_values = tf.reduce_sum(unsummed_kl, [-1, -2])
    return kl_values

def _js_2d(p, q, eps=1e-24):
    m = 0.5 * (p + q)
    return 0.5 * _kl_2d(p, m, eps) + 0.5 * _kl_2d(q, m, eps)

def _softmax2d(target, axes):

    max_axis = tf.reduce_max(target, axes, keepdims=True)
    target_exp = tf.exp(target-max_axis)
    normalize = tf.reduce_sum(target_exp, axes, keepdims=True)
    softmax = target_exp / normalize
    return softmax

def _make_gaussian(size, centre, fwhm=1):

        centre = [centre[0] * tf.cast(size[1], tf.float32), 
                  centre[1] * tf.cast(size[0], tf.float32)]
        square_size = tf.cast(tf.reduce_max(size), tf.float32)

        x = tf.range(0, square_size, 1, dtype=tf.float32)
        y = x[:,tf.newaxis]
        x0 = centre[0] - 0.5
        y0 = centre[1] - 0.5
        unnorm = tf.exp(-4*tf.log(2.) * ((x-x0)**2 + (y-y0)**2) / fwhm**2)[:size[0],:size[1]]
        norm = unnorm / tf.reduce_sum(unnorm)
        return norm

def _make_gaussians(centres_in, height, width, fwhm=1):

    def cond(centres, heatmaps):
        return tf.greater(tf.shape(centres)[0], 0)


    def body(centres, heatmaps):
        curr = centres[0]
        centres = centres[1:]
        new_heatmap = _make_gaussian([height, width], curr, fwhm)
        new_heatmap = tf.reshape(new_heatmap, [-1])
        
        heatmaps = tf.concat([heatmaps, new_heatmap], 0)



        return [centres, heatmaps]

    _, heatmaps_out = tf.while_loop(cond,
                                    body,
                                    [centres_in, tf.constant([])],
                                    shape_invariants=[tf.TensorShape([None, 2]), tf.TensorShape([None])])
    heatmaps_out = tf.reshape(heatmaps_out, [-1, height, width])
    return heatmaps_out
