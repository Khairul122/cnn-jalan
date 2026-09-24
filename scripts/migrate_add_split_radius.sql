-- Grup spasial pada split: foto yang berjarak <= radius_grup_m dipaksa satu fold (cegah kebocoran autokorelasi spasial).
ALTER TABLE split_config ADD COLUMN radius_grup_m INT NOT NULL DEFAULT 0 AFTER random_state;
