import argparse
import os


def truncate_pwl(input_file_path, truncation_us):
  """Truncates a PWL file to a specified number of microseconds,

  after shifting the time column so the minimum time starts at 0.
  """
  max_time_sec = truncation_us * 1e-6

  # Generate output filename: e.g., current.pwl -> current_750us.pwl
  base_name, ext = os.path.splitext(input_file_path)
  output_file_path = f"{base_name}_{int(truncation_us)}us{ext}"

  # Pass 1: Read all lines, parse data points, and find the minimum time value
  lines_data = []
  time_values = []

  with open(input_file_path, "r") as infile:
    for line in infile:
      stripped = line.strip()

      # Pass through empty lines or comments safely
      if not stripped or stripped.startswith(("*", ";", "#")):
        lines_data.append((line, None, None))
        continue

      parts = stripped.split()
      if len(parts) >= 2:
        try:
          time_val = float(parts[0])
          lines_data.append((line, time_val, parts))
          time_values.append(time_val)
        except ValueError:
          # If a line cannot be parsed as a float, keep it as-is
          lines_data.append((line, None, None))
      else:
        lines_data.append((line, None, None))

  if not time_values:
    print("Error: No valid time-value data points found in the PWL file.")
    return

  # Find the minimum value in the 1st column
  min_time = min(time_values)

  # Pass 2: Shift times, filter by truncation limit, and write to output file
  lines_written = 0
  with open(output_file_path, "w") as outfile:
    for line, time_val, parts in lines_data:
      if time_val is not None:
        # Subtract the minimum time from the 1st column
        shifted_time = time_val - min_time

        if shifted_time <= max_time_sec:
          # Replace the original time with the shifted time while preserving line formatting
          new_line = line.replace(parts[0], f"{shifted_time}", 1)
          outfile.write(new_line)
          lines_written += 1
        else:
          # Since the file is sorted by time, we can stop early once past the limit
          break
      else:
        # Write headers, comments, and empty lines through
        outfile.write(line)

  print(
      f"Success! Shifted (min time subtracted) & truncated file saved as:"
      f" {output_file_path} ({lines_written} data points kept)"
  )


if __name__ == "__main__":
  parser = argparse.ArgumentParser(
      description=(
          "Shift PWL time column to start at 0 and truncate to a specified"
          " microsecond limit."
      )
  )
  parser.add_argument(
      "file_path", type=str, help="Path to the input .pwl file."
  )
  parser.add_argument(
      "truncation_us",
      type=float,
      help="Truncation time in microseconds (e.g., 750).",
  )

  args = parser.parse_args()
  truncate_pwl(args.file_path, args.truncation_us)