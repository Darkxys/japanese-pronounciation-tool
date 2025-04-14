import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import numpy as np
import matplotlib

from sentence import Sentence, generate_julius_transcript_from_words, parse_words

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sounddevice as sd
import parselmouth
import wave
import os
import tempfile
from samples import Samples
from speech_record import SpeechRecord


class LivePitchAccentApp:
    def __init__(self, root):
        # Load samples
        self.samples = Samples().samples  # samples is a dict[string, dict]
        # Use "Forvo" as our sample source (adjust as needed)
        self.sample_source = "Forvo"

        self.root = root
        self.root.title("Live Pitch Analysis with Student Segmentation")

        # Main frame configuration
        self.mainframe = ttk.Frame(root, padding="10")
        self.mainframe.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        # Re-arrange grid rows:
        # Row 0: Buttons and sample selection
        # Row 1: Label for selected option
        # Row 2: Play Sample button
        # Row 3: Status label
        # Row 4: Matplotlib canvas (set to expand)
        self.mainframe.rowconfigure(5, weight=1)
        for col in range(2):
            self.mainframe.columnconfigure(col, weight=1)

        # Buttons: Start and Stop recording
        self.start_button = ttk.Button(
            self.mainframe, text="Start", command=self.start_recording
        )
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        self.stop_button = ttk.Button(
            self.mainframe, text="Stop", command=self.stop_recording, state="disabled"
        )
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

        # Sample selection: Create a label and a combobox.
        # Use keys of samples["Forvo"] (if available) as options.
        if self.sample_source in self.samples:
            sentence_keys = list(self.samples[self.sample_source].keys())
        else:
            sentence_keys = []

        self.sample_var = tk.StringVar(value=sentence_keys[0] if sentence_keys else "")
        self.sample_label = ttk.Label(self.mainframe, text="Select Sample:")
        self.sample_label.grid(row=1, column=0)

        self.sample_combobox = ttk.Combobox(
            self.mainframe, textvariable=self.sample_var, state="readonly"
        )
        self.sample_combobox["values"] = sentence_keys
        # Allow the combobox to expand horizontally.
        self.sample_combobox.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.sample_combobox.bind("<<ComboboxSelected>>", self.on_sample_selected)

        # Button to play the WAV file associated with the selected sample.
        self.play_button = ttk.Button(
            self.mainframe, text="Play Sample", command=self.play_sample_audio
        )
        self.play_button.grid(row=2, column=0, columnspan=4, padx=5, pady=5)

        # Status label.
        self.sentence_label = ttk.Label(self.mainframe, text="")
        self.sentence_label.grid(row=3, column=0, columnspan=4, padx=5, pady=5)
        self.status_label = ttk.Label(
            self.mainframe, text="Press 'Start' to begin recording."
        )
        self.status_label.grid(row=4, column=0, columnspan=4, padx=5, pady=5)

        # Matplotlib figure with two subplots: one for pitch and one for intensity.
        self.figure = plt.Figure()
        self.ax_pitch = self.figure.add_subplot(111)

        # Configure pitch subplot.
        self.ax_pitch.set_title("Live Pitch Contour")
        self.ax_pitch.set_ylabel("Pitch (Hz)")
        self.ax_pitch.set_ylim(0, 300)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.mainframe)
        self.canvas.get_tk_widget().grid(
            row=5, column=0, columnspan=4, sticky="nsew", padx=5, pady=5
        )

        # Audio parameters and buffer.
        self.fs = 16000
        self.channels = 1
        self.blocksize = 1024
        self.full_buffer = []
        self.is_recording = False
        self.stream = None

        # This attribute will hold the fetched sample data after selection.
        self.selected_sample = None
        self.teacher_rec = None

    def play_sample_audio(self):
        """Plays the WAV file of the selected sample.
        Assumes the sample dictionary contains a key 'wav' with the file path.
        """
        if not self.selected_sample:
            messagebox.showwarning(
                "No Sample Selected", "Please select a sample first."
            )
            return

        wav_file = self.selected_sample.get("filename")
        if not wav_file or not os.path.exists(wav_file):
            messagebox.showerror(
                "Error", "Selected sample does not have a valid WAV file."
            )
            return

        try:
            with wave.open(wav_file, "rb") as wf:
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                audio_data = wf.readframes(nframes)
                # Assuming 16-bit PCM data.
                audio_np = (
                    np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32767
                )
            sd.play(audio_np, framerate)
            sd.wait()  # Wait until playback is finished.
        except Exception as e:
            messagebox.showerror("Playback Error", f"Error playing audio: {e}")

    def convert_sentence(self, sentence):
        return generate_julius_transcript_from_words(parse_words(sentence))

    def on_sample_selected(self, event):
        """Callback when a sample is selected from the combobox.
        It fetches the sample data from samples[self.sample_source][selected_sentence].
        """
        selected_sentence = self.sample_var.get()
        if (
            self.sample_source in self.samples
            and selected_sentence in self.samples[self.sample_source]
        ):
            sample_data = self.samples[self.sample_source][selected_sentence]
            self.selected_sample = sample_data

            sentence = Sentence(sample_data["sentence"])
            self.teacher_rec = SpeechRecord(sample_data["filename"], sentence)

            self.sentence_label.config(
                text=f"Selected Sample: {sentence.get_hepburn_transcript()}"
            )
            # You can now further process or display sample_data as needed.
        else:
            messagebox.showwarning("Selection Error", "Selected sample not found.")

    def start_recording(self):
        if self.is_recording:
            return
        self.is_recording = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_label.config(text="Recording...")
        self.full_buffer = []

        try:
            self.stream = sd.InputStream(
                samplerate=self.fs,
                channels=self.channels,
                blocksize=self.blocksize,
                dtype="float32",
                callback=self.audio_callback,
            )
            self.stream.start()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open microphone: {e}")
            self.stop_recording()
            return
        self.update_plot()

    def stop_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_label.config(text="Recording stopped.")
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.process_recording()

    def audio_callback(self, indata, frames, time, status):
        if not self.is_recording:
            return
        data_np = indata[:, 0]
        self.full_buffer.extend(data_np.tolist())

    def update_plot(self):
        if not self.is_recording:
            return

        audio_data = (
            np.array(self.full_buffer, dtype=np.float32)
            if self.full_buffer
            else np.array([], dtype=np.float32)
        )

        # Update live pitch analysis
        times, pitch_values = self.analyze_pitch(audio_data, self.fs)
        if times is not None and pitch_values is not None:
            self.ax_pitch.clear()
            self.ax_pitch.plot(times, pitch_values)
            self.ax_pitch.set_title("Live Pitch Contour")
            self.ax_pitch.set_ylabel("Pitch (Hz)")
            self.ax_pitch.set_ylim(0, 300)

        self.canvas.draw()
        self.root.after(100, self.update_plot)

    def analyze_pitch(self, audio_data, sr):
        try:
            sound = parselmouth.Sound(audio_data, sr)
            pitch = sound.to_pitch(time_step=0.01, pitch_floor=50, pitch_ceiling=500)
            pitch_values = pitch.selected_array["frequency"]
            pitch_values = np.where(pitch_values == 0, np.nan, pitch_values)
            times = pitch.xs()
            return times, pitch_values
        except Exception:
            return None, None

    def analyze_intensity(self, audio_data, sr):
        try:
            sound = parselmouth.Sound(audio_data, sr)
            intensity = sound.to_intensity(time_step=0.01, minimum_pitch=10)
            intensity_values = np.array(intensity.values).flatten()
            intensity_values = np.where(intensity_values < 10, None, intensity_values)
            times = intensity.xs()
            return times, intensity_values
        except Exception:
            return None, None

    def process_recording(self):
        """
        Called after recording stops.
        Saves the captured audio to a temporary WAV file,
        asks for a transcript to segment the student recording,
        creates a SpeechRecord, and then updates the graphs to show
        the pitch contour with overlaid phoneme segmentation.
        """
        if len(self.full_buffer) == 0:
            messagebox.showwarning("No Audio", "No audio captured.")
            return

        tmp_wav = os.path.join(tempfile.gettempdir(), "student_recording.wav")
        try:
            with wave.open(tmp_wav, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit PCM
                wf.setframerate(self.fs)
                # Convert the float32 audio (range -1.0 to 1.0) to int16.
                audio_int16 = (np.array(self.full_buffer) * 32767).astype(np.int16)
                wf.writeframes(audio_int16.tobytes())
        except Exception as e:
            messagebox.showerror("Error", f"Could not save recording: {e}")
            return

        try:
            # Create the SpeechRecord for the student recording using the provided transcript.
            student_record = SpeechRecord(tmp_wav, self.selected_sample["sentence"])
        except Exception as e:
            messagebox.showerror("Error", f"Error processing student recording: {e}")
            return

        # Update the plot with student pitch and overlay the phoneme segmentation.
        self.plot_student_segmentation(student_record)

    def plot_student_segmentation(self, student_record: SpeechRecord):
        """
        Update the figure to show the student pitch contour and overlay the phoneme segmentation.
        Vertical dashed lines mark the phoneme boundaries and labels display the phoneme.
        """
        student_record.align_with(self.teacher_rec)
        self.ax_pitch.clear()

        # Plot the student pitch contour.
        self.ax_pitch.plot(
            student_record.align_ts,
            student_record.norm_aligned_pitch,
            label="Student Pitch",
            color="green",
        )
        self.ax_pitch.plot(
            student_record.align_ts,
            student_record.ref_rec.norm_aligned_pitch,
            label="Teacher Pitch",
            color="blue",
        )

        self.ax_pitch.set_title("Student's Pitch vs Teacher's Pitch")
        self.ax_pitch.set_ylabel("Pitch")
        self.ax_pitch.set_ylim(-5, 5)
        self.ax_pitch.legend()

        self.status_label.config(
            text=f"Student Pitch Similarity: {int(student_record.compare_pitch() * 100)}%"
        )

        # If phoneme segmentation is available, update the x-axis ticks.
        if student_record.phonemes:
            tick_positions = []
            tick_labels = []
            for start, end, pho in student_record.phonemes:
                # Draw vertical dashed lines at the phoneme boundaries (optional).
                self.ax_pitch.axvline(x=start, color="gray", linestyle="--", alpha=0.7)
                # Use the midpoint between start and end as the tick position.
                tick_positions.append((start + end) / 2)
                tick_labels.append(pho)
            self.ax_pitch.set_xticks(tick_positions)
            self.ax_pitch.set_xticklabels(tick_labels)

        self.canvas.draw()


if __name__ == "__main__":
    try:
        root = tk.Tk()
        root.geometry("600x600")
        app = LivePitchAccentApp(root)
        root.mainloop()
    except Exception as e:
        print(e)
