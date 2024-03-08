import json
import re
import pdb

test_sample_id = [3, 5, 6, 20, 23, 25, 29, 31, 34, 42, 48, 54, 60, 66, 69, 80, 84, 92, 96, 100]
all_scores = []
directory_path = f'./your_workspace'
for idx in range(1, 101):
    directory = f'{directory_path}/example_{idx}'
    # Path to your log file
    log_file_path = directory + '/eval_4v_rollback.log'

    # Read the log file
    with open(log_file_path, 'r') as file:
        log_contents = file.read()

    # Regular expression to match evaluation settings and scores
    # pattern = r'Evaluating (gpt-(?:4|3\.5-turbo) \w+).*?\[FINAL SCORE\]: (\d{1,3})'
    pattern = r'Evaluating (gpt-4_llava-v1.6-34b \w+).*?\[FINAL SCORE\]: (\d{1,3})'

    # Find all matches
    matches = re.findall(pattern, log_contents, re.DOTALL)

    # Create a dictionary to store settings and their scores
    scores = {}
    scores.update({'id': idx})
    for setting, score in matches:
        scores[setting] = int(score)
    # pdb.set_trace()
    # scores['id'] = idx

    # print(scores)
    all_scores.append(scores)

with open(f"{directory_path}/automatic_eval_rollback.json", 'w') as f:
    json.dump(all_scores, f, indent=4, ensure_ascii=False)

data = all_scores

# Initialize a dictionary to store total scores and counts
total_scores = {}
count = {}
idx = 1
undone_list = []

# Aggregate scores
for entry in data:
    # pdb.set_trace()
    if len(entry.items()) == 2:
        for setting, score in entry.items():
            if setting not in total_scores:
                total_scores[setting] = 0
                count[setting] = 0
            total_scores[setting] += score
            count[setting] += 1
        idx += 1
    else:
        undone_list.append(idx)
        idx += 1


# Calculate averages
average_scores = {setting: total_scores[setting] / count[setting] for setting in total_scores}

print('average scores:')
print(average_scores)
# print(undone_list)
