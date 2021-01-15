import json
import codecs
import torch
import numpy as np
import argparse
import os
# import matplotlib
# import matplotlib.pyplot as plt
from pathlib import Path
from utils import plot_stroke
from utils.constants import Global
from utils.dataset import HandwritingDataset
from utils.data_utils import data_denormalization, data_normalization
from models.models import HandWritingPredictionNet, HandWritingSynthesisNet


def argparser():

    parser = argparse.ArgumentParser(
        description="PyTorch Handwriting Synthesis Model")
    parser.add_argument("--model", type=str, default="synthesis")
    parser.add_argument(
        "--model_path",
        type=Path,
        default="./pretrained/model_synthesis.pt"
    )
    parser.add_argument("--save_path", type=Path, default="./results/")
    parser.add_argument("--seq_len", type=int, default=400)
    # parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--bias", type=float, default=10.0, help="bias")
    parser.add_argument("--char_seq", type=str,
                        default="A sample of generated handwriting")
    parser.add_argument("--text_req", action="store_true")
    # parser.add_argument("--prime", action="store_true")
    # parser.add_argument("--is_map", action="store_true")
    parser.add_argument("--seed", type=int, help="random seed")
    parser.add_argument("--data_path", type=str, default="./data/")
    # parser.add_argument("--file_path", type=str, help="./app/")
    parser.add_argument("--style", type=int, help="style number [0,4]")
    parser.add_argument("--save_img", action="store_true")
    args = parser.parse_args()

    return args


def generate_unconditional_seq(model_path, seq_len, device, bias, style,
                               prime):

    model = HandWritingPredictionNet()
    # load the best model
    model.load_state_dict(torch.load(model_path, map_location=device))
    model = model.to(device)
    model.eval()

    # initial input
    inp = torch.zeros(1, 1, 3)
    inp = inp.to(device)

    batch_size = 1

    initial_hidden = model.init_hidden(batch_size, device)

    print("Generating sequence....")
    gen_seq = model.generate(inp, initial_hidden, seq_len, bias, style, prime)

    return gen_seq


def generate_conditional_sequence(model_path, char_seq, device, char_to_id,
                                  idx_to_char, bias, prime, prime_seq,
                                  real_text, batch_size=1):  # is_map,

    model = HandWritingSynthesisNet(window_size=len(char_to_id))
    # load the best model
    model.load_state_dict(torch.load(model_path, map_location=device))

    # Print model's state_dict
    # print(f"Model's state_dict:")
    # for param_tensor in model.state_dict():
    #     print(f"{param_tensor}\t {model.state_dict()[param_tensor]}")

    model = model.to(device)
    model.eval()

    # initial input
    if prime:
        inp = prime_seq
        real_seq = np.array(list(real_text))
        idx_arr = [char_to_id[char] for char in real_seq]
        prime_text = np.array(
            [idx_arr for i in range(batch_size)]).astype(np.float32)
        prime_text = torch.from_numpy(prime_text).to(device)
        prime_mask = torch.ones(prime_text.shape).to(device)
    else:
        prime_text = None
        prime_mask = None
        inp = torch.zeros(batch_size, 1, 3).to(device)

    char_seq = np.array(list(char_seq + "  "))
    print("".join(char_seq))
    text = np.array(
        [[char_to_id[char] for char in char_seq] for i in range(batch_size)]
    ).astype(np.float32)
    text = torch.from_numpy(text).to(device)

    text_mask = torch.ones(text.shape).to(device)

    hidden, window_vector, kappa = model.init_hidden(batch_size, device)

    print("Generating sequence....")
    gen_seq = model.generate(inp, text, text_mask, prime_text, prime_mask,
                             hidden, window_vector, kappa, bias,  # TODO
                             prime=prime)  # is_map,

    # length = len(text_mask.nonzero())
    length = len(torch.nonzero(text_mask, as_tuple=False).to(text_mask.device))
    print("Input text:", "".join(idx_to_char(
        text[0].detach().cpu().numpy()))[:length])
    print("Length of input text:", text[0].shape[0])

    # if is_map:
    #     phi = torch.cat(model._phi, dim=1).cpu().numpy()
    #     phi = phi[0].T
    # else:
    #     phi = []

    return gen_seq  # , phi


if __name__ == "__main__":

    args = argparser()
    if not args.save_path.exists():
        args.save_path.mkdir(parents=True, exist_ok=True)

    # fix random seed
    if args.seed:
        torch.manual_seed(args.seed)
        np.random.seed(args.seed)

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    model_path = args.model_path
    model = args.model
    prime = True if args.style is not None else False

    train_dataset = HandwritingDataset(
        args.data_path, split="train", text_req=args.text_req
    )

    if args.style is not None:  # args.prime and
        # style = np.load(
        #     args.file_path + "style.npy", allow_pickle=True, encoding="bytes"
        # ).astype(np.float32)
        # with open(args.file_path + "inpText.txt") as file:
        #     texts = file.read().splitlines()
        # real_text = texts[0]
        styles = np.load('./styles/style_strokes.npy', allow_pickle=True)
        texts = np.load('./styles/style_sents.npy', allow_pickle=True)
        real_text = texts[args.style]
        style = styles[args.style]
        # plot the sequence
        # plot_stroke(style, save_name=args.save_path / "style.png")
        # print(real_text)
        mean, std, _ = data_normalization(style)
        style = np.expand_dims(style, axis=0)
        # style = np.array([style for i in range(args.batch_size)])
        style = torch.from_numpy(style).to(device)
        # style = torch.from_numpy(style).unsqueeze(0).to(device)
        # print(style.shape)
        ytext = real_text + " " + args.char_seq + "  "
    # elif args.prime:
    #     strokes = np.load(
    #       args.data_path + "strokes.npy", allow_pickle=True, encoding="bytes"
    #     )
    #     with open(args.data_path + "sentences.txt") as file:
    #         texts = file.read().splitlines()
    #     idx = np.random.randint(0, len(strokes))
    #     print("Prime style index: ", idx)
    #     real_text = texts[idx]
    #     style = strokes[idx]
    #     # plot the sequence
    #     plot_stroke(style, save_name=args.save_path /
    #                 ("style_" + str(idx) + ".png"))
    #     print(real_text)
    #     mean, std, _ = data_normalization(style)
    #     style = np.array([style for i in range(args.batch_size)])
    #     style = torch.from_numpy(style).to(device)
    #     print(style.shape)
    #     ytext = real_text + " " + args.char_seq + "  "
    else:
        idx = -1
        real_text = ""
        style = None
        ytext = args.char_seq + "  "

    if model == "prediction":
        gen_seq = generate_unconditional_seq(model_path, args.seq_len, device,
                                             args.bias, style=style,
                                             prime=prime)
    elif model == "synthesis":
        gen_seq = generate_conditional_sequence(model_path, args.char_seq, # , phi
                                                device,
                                                train_dataset.char_to_id,
                                                train_dataset.idx_to_char,
                                                args.bias, prime,
                                                style, real_text)
                                                # False,              # TODO: Remove args.is_map's trace
                                                # args.batch_size)
        # if args.is_map:
        #     plt.imshow(phi, cmap="viridis", aspect="auto")
        #     plt.colorbar()
        #     plt.xlabel("time steps")
        #     plt.yticks(np.arange(phi.shape[0]), list(
        #         ytext), rotation="horizontal")
        #     plt.margins(0.2)
        #     plt.subplots_adjust(bottom=0.15)
        #     plt.savefig("heat_map.png")
        #     plt.close()

    # denormalize the generated offsets using train set mean and std
    # if args.prime:
    #     print("data denormalization...")
    #     gen_seq = data_denormalization(mean, std, gen_seq)
    # else:
    gen_seq = data_denormalization(
        Global.train_mean, Global.train_std, gen_seq)
    gen_seq = np.squeeze(gen_seq)

    # plot the sequence
    if args.save_img:
        img_path = os.path.join(str(args.save_path),
                                "gen_img.png")
        plot_stroke(gen_seq, save_name=img_path)
        print(f"Image saved as: {img_path}")

    # Export generated sequence as json
    seq_list = gen_seq.tolist()
    json_file_path = os.path.join(str(args.save_path), "generated_seq.json")
    json.dump(seq_list,
              codecs.open(json_file_path, 'w', encoding='utf-8'),
              separators=(',', ':'), sort_keys=True, indent=4)
    print(f"Sequence saved to json: {json_file_path}")

    # for i in range(args.batch_size):
    #     if args.save_img:
    #         # plot the sequence
    #         img_path = os.path.join(str(args.save_path),
    #                                 "gen_img_" + str(i) + ".png")
    #         plot_stroke(gen_seq[i], save_name=img_path)
    #         print(f"Image {i} saved as: {img_path}")

    #     seq_list = gen_seq[i].tolist()
    #     json_file_path = os.path.join(str(args.save_path),
    #                                   "generated_seq_" + str(i) + ".json")
    #     json.dump(seq_list,
    #               codecs.open(json_file_path, 'w', encoding='utf-8'),
    #               separators=(',', ':'), sort_keys=True, indent=4)
    #     print(f"Sequence {i} saved to json: {json_file_path}")
